# Offline sample dataset

`usgs_2025_q1_m5plus.csv` contains 396 catalog events returned by the USGS FDSN Event Web Service on 2026-09-30. It is a static snapshot of the global query from 2025-01-01 00:00 UTC through the 2025-04-01 00:00 UTC boundary (events through March 31), minimum magnitude 5, with the service's preferred event solutions.

Source query: [USGS FDSN Event Web Service](https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2025-01-01&endtime=2025-04-01&minmagnitude=5&limit=2000&orderby=time).

Fields are copied from GeoJSON feature IDs, properties, and point coordinates. Coordinates are stored as latitude/longitude in decimal degrees and depth in km. Missing magnitude, depth, magnitude type, or descriptive fields remain blank. Catalog records may be revised after this snapshot was collected; live mode requests current preferred solutions.
