"""Figure of merit code

In general, this module contains components to implement the following flow: 
    + add a column to the fire_events table to store the points projected into
      the NLCD projection.
    + create two fire_events_rasters serving as a fire mask for 750m and 
      375m fire events points.
    + combine the two fire events rasters on a 375m grid.
    + perform intersections and unions between the combined satellite 
      fire mask and the ground truth fire mask.
    + sum all the active fire pixels in the intersection and the union.
    + ratio the sum of the intersection pixels to the sum  of union pixels.

A second figure of merit flow is as follows: 
    + add a column to the fire_events table to store the points projected into
      the NLCD projection.
    + create two fire_events_rasters serving as a fire mask for 750m and 
      375m fire events points.
    + combine the two fire events rasters on a 375m grid.
    + sum all "true" points in the combined fire events mask on a per zone
      basis, storing the results in a table
"""

import os.path
import numpy as np
import pandas as pd
import psycopg2
import multiprocessing as mp
import functools as ft
import VIIRS_threshold_reflCor_Bulk as vt
import viirs_config as vc


def extract_fire_mask(config, gt_schema, gt_table,rast_col='rast',geom_col='geom') : 
    """Creates a geometry column and populates with pixel centers where pixel value=1"""
    query="SELECT viirs_get_mask_pts('{0}', '{1}', '{2}', '{3}', {4})".format(
         gt_schema, gt_table, rast_col, geom_col, vt.srids['NLCD'])
    vt.execute_query(config, query) 

def project_fire_events_nlcd(config) :
    """Creates a new geometry column in the fire_events table and project to
    NLCD coordinates."""
    
    query = "SELECT viirs_nlcd_geom('{0}', 'fire_events', {1})".format(config.DBschema, vt.srids["NLCD"])
    vt.execute_query(config, query)

def create_fire_events_raster(config, gt_schema, gt_table) : 
    """dumps the ground truth fire mask to disk, overwrites by rasterizing fire_events, 
    reloads the table to postgis
    This ensures that the result is aligned to the specified ground truth 
    table."""

    query = "SELECT viirs_rasterize_375('{0}', '{1}', '{2}', {3})".format(
          config.DBschema, gt_schema, gt_table, config.SpatialProximity)
    vt.execute_query(config, query)

    query = "SELECT viirs_rasterize_750('{0}', '{1}', '{2}', {3})".format(
          config.DBschema, gt_schema, gt_table, config.SpatialProximity)
    vt.execute_query(config, query)

    query = "SELECT viirs_rasterize_merge('{0}')".format(config.DBschema)
    vt.execute_query(config, query)
    
def mask_sum(config, gt_schema, gt_table) : 
    """adds the mask values from the fire_events_raster to the values in the ground truth raster.
    
    The fire events raster is in config.DBschema. The ground truth raster to use
    is provided in gt_schema and gt_table. If the supplied masks have only 0 and 1
    in them, as they should, then the sum raster should have only 0, 1, and 2.
    The logical "or" function between the two masks is the set of pixels having a
    nonzero value. The logical "and" function is the set of pixels having the value
    two."""
    query = "SELECT viirs_mask_sum('{0}', '{1}', '{2}')".format(
         config.DBschema, gt_schema, gt_table)
    vt.execute_query(config,query)
    
def calc_ioveru_fom(config) :  
    """calculates the intersection over union figure of merit.
    This function assumes that the mask_sum raster already exists in the 
    database. Returns a floating point number from 0..1"""
    query = "SELECT viirs_calc_fom('{0}')".format(config.DBschema)
    
    # now, need to execute a query that returns a single result.
    ConnParam = vt.postgis_conn_params(config)
    conn = psycopg2.connect(ConnParam)
    # Open a cursor to perform database operations
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()

    conn.commit()
    # Close communication with the database
    cur.close()
    conn.close()
    
    return rows[0][0]
    
    
def do_ioveru_fom(gt_schema, gt_table, config) : 
    """performs the complete process for calculating the intersection over union
    figure of merit."""
    
    project_fire_events_nlcd(config)
    create_fire_events_raster(config, gt_schema, gt_table)
    mask_sum(config, gt_schema, gt_table)
    return calc_ioveru_fom(config)

def zonetbl_init(zone_schema, zone_tbl, config) : 
    """drops and re-creates the table in which results are accumulated"""
    query = "SELECT viirs_zonetbl_init('{0}', '{1}', {2})".format(
           zone_schema, zone_tbl, vt.srids['NLCD'])
    vt.execute_query(config, query)

def zonetbl_run(zone_schema, zonedef_tbl, zone_tbl, zone_col, config) : 
    run_schema = config.DBschema
    
    query="SELECT viirs_zonetbl_run('{0}','{1}','{2}','{3}','{4}')".format(
        zone_schema, zone_tbl, zonedef_tbl, run_schema, zone_col)
    vt.execute_query(config, query)

def do_one_zonetbl_run(gt_schema, zonedef_tbls, zone_tbls, zone_cols, config):
    """accumulates fire points from a single run into one or more zone tables.
    The zone definition table, results accumulation table, and column names
    are specified as parallel lists in zonedef_tbls, zone_tbls, zone_cols.
    """
    extract_fire_mask(config, config.DBschema, 'fire_events_raster',
                       geom_col='geom_nlcd')
    # try treating deftbls, tbls, and cols as parallel lists
    for deftbl,tbl,col in zip(zonedef_tbls,zone_tbls,zone_cols) : 
        zonetbl_run(gt_schema, deftbl, tbl, col, config)
    
def calc_all_ioveru_fom(run_datafile, gt_schema, gt_table, workers=1) : 
    """calculates the i over u figure of merit for a batch of previously
    completed runs.
    User supplies the path name of a previously written CSV file which 
    describes a batch of runs. The directory containing this file must
    also contain a bunch of run directories, each of which contains an
    *.ini file for the run."""
    # find where we are
    base_dir = os.path.dirname(run_datafile)
    if base_dir == '' : 
        base_dir = '.'

    runlist = pd.read_csv(run_datafile, index_col=0) 
    fomdata = np.zeros_like(runlist['run_id'],dtype=np.float)
    config_list = vc.VIIRSConfig.load_batch(base_dir)

    # prep ground truth table, giving each row a multipoint
    # geometry of the centroids of "true" pixels in the mask
    extract_fire_mask(config, gt_schema, gt_table)

    workerfunc = ft.partial(do_ioveru_fom, gt_schema, gt_table)

    if workers == 1 : 
        fom = map(workerfunc, config_list)

    else : 
        mypool = mp.Pool(processes=workers) 
        fom = mypool.map(workerfunc, config_list)

    for i in range(len(config_list)) : 
        row = np.where(runlist['run_id'] == config_list[i].run_id)
        fomdata[row] = fom[i]
 
    runlist['fom'] = pd.Series(fomdata, index=runlist.index)
    newname = 'new_{0}'.format(os.path.basename(run_datafile))
    runlist.to_csv(os.path.join(base_dir, newname))

def do_all_zonetbl_runs(base_dir, gt_schema, workers=1) : 
    """accumulates fire event raster points by polygon-defined zones.
    This function relies on the rasterized fire events tables created
    by the do_ioveru_fom() method. Make sure that these tables exist.
    """
    config_list = vc.VIIRSConfig.load_batch(base_dir)

    # prepare the table to accumulate results
    zonetbl_init(gt_schema, 'eval_zone_counts', config_list[0])

    workerfunc = ft.partial(do_one_zonetbl_run, gt_schema,
                      ('dissolve_eval_zones',),
                      ('eval_zone_counts',),
                      ('zone',))

    if workers == 1 : 
        map(workerfunc, config_list)
    else:  
        mypool = mp.Pool(processes=workers)
        mypool.map(workerfunc,config_list)
