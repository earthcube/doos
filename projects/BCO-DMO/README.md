# BCO-DMO

## TODO

- [ ] bring over playwright code or lightpanda 
  - docker run -d --name lightpanda -p 9222:9222 lightpanda/browser:nightly
- [ ] query for distribution and download

BCO-DMO metadata architecture.
* There are now dedicated URLs for metadata based on S3 access key approaches
* These are not SOSO/JSON-LD however.  (ISO115, PDF and Frictionless)
  * Side point:  The PDF is some interesting LLM Foder
* The JSON-LD loading seems to be a lazy JS load.

## Notes

### ERDDAP notes

* https://erddap.bco-dmo.org/erddap/tabledap/bcodmo_dataset_473296.html
* https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_473296/index.html
* https://erddap.bco-dmo.org/erddap/rest.html


### Langchain

Langchain is much faster as it has a dedicated Pandas agent.  So it seems to stay focused on the task better. 

Run time is around 4 seconds.

### RLM

The RLM approach works, but it takes more time since it is a general REPL that resolves out the approach needed to address the task.  So it is many times slower than the Langchain approach since it generates the code in real time to address the request.  

However, we might be able to address this using some of the "pandas ai" libraries directly with DSPy and not leveraging the generic RLM capacity.


### References

Going to start a project with BCO-DMO to augment data from their data resources into the metadata.  

https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1

https://www.bco-dmo.org/doi/dataset/file-download/10.26008/1912/bco-dmo.990510.1/package/public/datapackage.json
