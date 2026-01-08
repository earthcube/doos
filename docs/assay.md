# Simply approach to assay data resources


## Notes


```bash
curl -s  --header "Accept: text/html"   https://obis.org/dataset/dac63ff7-e96f-41fa-8ba9-710c7a92d098 | sed -n '/<script type=\"application\/ld+json\">/,/<\/script>/p' | sed 's/<\/script>//' | sed 's/<script type=\"application\/ld+json\">//' | jsonld format -q
```


```bash
curl -s  --header "Accept: text/html"   "https://oss.geocodes-aws-dev.earthcube.org/geocodes/summoned%2Fbodc%2Fffac803ba549b522c0897a8fde842bdbe4bbb113.jsonld"  | jsonld format  
```


