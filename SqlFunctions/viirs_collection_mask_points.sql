CREATE OR REPLACE FUNCTION viirs_collection_mask_points(
    varchar(200),
    text,
    text,
    text,
    text,
    timestamp without time zone)
  RETURNS void AS
$BODY$
DECLARE
  schema varchar(200) := $1;
  point_tbl text := $2 ;
  landcover_schema text := $3;
  no_burn_table text := $4 ; 
  no_burn_geom text := $5 ; 
  collection timestamp without time zone := $6 ;
  no_burn_res real ;
  dumint int ;  

BEGIN

  -- determine the srid of the landcover mask for projection
  EXECUTE 'SELECT ST_SRID(rast) FROM ' || 
     quote_ident(landcover_schema)||'.'||quote_ident(no_burn_table)||' nb ' || 
     'LIMIT 1' INTO dumint ; 

  -- reproject and index the points
  PERFORM viirs_collection_nlcd_geom(schema, point_tbl, dumint, collection) ;


  -- determine resolution of "no-burn" mask
  EXECUTE 'SELECT scale_x/2 FROM raster_columns WHERE r_table_schema = ' || 
      quote_literal(landcover_schema) || 
      ' AND r_table_name = ' || quote_literal(no_burn_table) || 
      ' AND r_raster_column = ' || quote_literal('rast') INTO no_burn_res ;

  -- Populate the masked column
  EXECUTE 'UPDATE ' || quote_ident(schema) || '.'||quote_ident(point_tbl)|| ' a '  || 
           'SET masked=TRUE ' ||
           'FROM ' ||quote_ident(landcover_schema)||'.'||quote_ident(no_burn_table)||' nb ' || 
           'WHERE a.geom_nlcd && nb.rast AND ' ||
        'ST_DWithin(a.geom_nlcd, nb.geom, $1) AND ' ||
        'collection_date = $2' 
    USING  no_burn_res, collection ; 
END
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION viirs_collection_mask_points(varchar(200),text,text,text,text,timestamp without time zone)
  OWNER TO postgres;

