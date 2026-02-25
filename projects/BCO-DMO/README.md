# BCO-DMO

## Notes

### ERDDAP notes

* https://erddap.bco-dmo.org/erddap/tabledap/bcodmo_dataset_473296.html
* https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_473296/index.html
* https://erddap.bco-dmo.org/erddap/rest.html
* 


### Langchain

Langchain is much faster as it has a dedeicated Pandas agent.  

### RLM

The RLM approach works but it takes more time since it is a general REPL that resolves out the approach needed to address the task.  So it is many times slower than the Langchain approach.

However, we might be able to address this using some of the "pandas ai" libraries directly with DSPy and not leveraging the generic RLM capacity.




### References

Going to start a project with BCO-DMO to augment data from their data resources into the metadata.  

https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1

https://www.bco-dmo.org/doi/dataset/file-download/10.26008/1912/bco-dmo.990510.1/package/public/datapackage.json

https://bcodmo-doi-prod.s3.amazonaws.com/990510_1_10.26008_dataset/datapackage_public.json?response-content-disposition=inline%3B%20filename%3D%22datapackage.json%22&AWSAccessKeyId=ASIAXLAGZQJYXLBYVVG6&Signature=4zKc0ZbyaYyYY1Nvxnr6eGOFFuQ%3D&x-amz-security-token=IQoJb3JpZ2luX2VjECYaCXVzLWVhc3QtMSJIMEYCIQDRyEtNUMJ57hqJJxclcX0%2FJEkxhe%2FmI0%2F%2BoR9Jd%2FtuzgIhAMx1wFjfvZbtVrmyW3E978s87ldCl%2F810Yz3DPbKzREWKosDCO%2F%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQBBoMNTA0NjcyOTExOTg1Igw3v%2F6RmhQgIYEICO0q3wKzb5aso3BP1T1gWW02j9h%2Buv4ydv0%2BBeJZlyCMbPEm8awUXIdFc%2B0SiU8R4xMqnPuLSzLd6uOt%2Fh3is0txnb%2F0dr9mEApGobXkXOtb8%2FtBvkqnx9bl3ETZ8niSX7YIVsgCmgLGkP6oC6lp%2BXbtB4B7s6e2uHm2mqltSB%2F7NUYF07E1jsAURbH10xyY21Z48QISkfT6LER%2FgDLvIMafSTbi7a2b6cGcrgSqyos6f4nTGL2K6aKie1Na3sDXd6BsThN3DsYm7V%2FVzwmHfZHr%2BbxoAv6KnoX%2BhcpEwH64pceijch2UcLY1aJfpgolqRpFz8%2F%2BjFWRF2N%2FyOPo7DDxWWvt2rbVWHfAgFW%2FkBUiGOA4IOsKbTFuxfPrUHFKsHW3aMaAfo5fkAL7FmzRNTORUmWUWGNHzAQyJf7BRgjnqO6M6rUXSTZpEktckhEzAbdVCYFxFqoxCXuqAvP5vMkKu%2F8w3868zAY6nQFmJkNV75WgE6fYYDryOS4GbH1Cd6f7ZYADkb5CnZlCgetR59sIqcvYA%2BE5UtCrQhdiLKsM0qSoGrfbd85lZqcuhi%2B6md45%2Blxt37%2FghnSuHT8RAc02KE7%2BoAfot4sHoJ7okTx0mKmn8fMz3gQlTQrLDGntoGaIVABJHwf67He%2BT60qFsLNVoUDQ3P2K9CwqXEZOHz8idMoYc1bw3Uj&Expires=1770993036
