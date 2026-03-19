# BCO-DMO

## Notes

### ERDDAP notes

* https://erddap.bco-dmo.org/erddap/tabledap/bcodmo_dataset_473296.html
* https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_473296/index.html
* https://erddap.bco-dmo.org/erddap/rest.html



### Langchain

Langchain is much faster as it has a dedeicated Pandas agent.  

### RLM

The RLM approach works but it takes more time since it is a general REPL that resolves out the approach needed to address the task.  So it is many times slower than the Langchain approach.

However, we might be able to address this using some of the "pandas ai" libraries directly with DSPy and not leveraging the generic RLM capacity.




### References

Going to start a project with BCO-DMO to augment data from their data resources into the metadata.  

https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1

https://www.bco-dmo.org/doi/dataset/file-download/10.26008/1912/bco-dmo.990510.1/package/public/datapackage.json
