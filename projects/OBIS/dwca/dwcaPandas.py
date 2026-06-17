from dwca.read import DwCAReader

with DwCAReader('./archive/dwca-smhi-zoobenthos-reg-v1.0.zip') as dwca:
   print("Core data file is: {}".format(dwca.descriptor.core.file_location)) # => 'occurrence.txt'

   core_df = dwca.pd_read('occurrence.txt', parse_dates=True)
   
   print(core_df.info())
   print(core_df.head())
   
   print(core_df['maximumDepthInMeters'].min())
   print(core_df['maximumDepthInMeters'].max())
