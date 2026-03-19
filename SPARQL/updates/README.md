# SPARQL updates

## About

How to run SPARQL updates.



# with all options:  
```bash
python insertUpdates.py \
    --token YOUR_TOKEN_HERE \
    --endpoint http://workstation.lan:7019 \
    --file output.nt \
    --batch-size 500 \
    --format ntriples
```

```bash
curl -X "POST" \
     -H "Content-Type: text/turtle" \
     -H "Authorization: Bearer {token}" \
     --data-binary @graph.ttl \
     "http://localhost:7019?graph=http://example.com/person/1.ttl"
```

## References

* https://docs.qlever.dev/rebuild-index/ 
