# Data Sourcing

So far, there are two functional data sources:
 - the [Commission's Funding & Tenders Portal ](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)
 - topic-specific manual data

Data sourcing is handled by the ```DataSource``` class in the ```data-sourcing.py``` file. For each data source, one should define a subclass inheriting ```DataSource``` conatining the constructor and the method ```load_saved_data``` which fetches the source from a file. It may also contain some update function which updates the file with content, e.g. downloaded from the web. 


## Funding and Tenders Portal 

In order to download all projects and participating organizations in the portal, the ```FundingAndTenderPortal```-class uses the API documented [here](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis).

As things stand now, the maximum number of projects returned by a query is limited to 10000. However, the total number of projects exceeds 70000. This is a problem, because the 10000 projects returned by a query may be a random selection of all projects. The API documentation does not present a solution to this problem and a clean path to downloading all projects and organizations from the portal. This is why the ```FundingAndTenderPortal```-class uses a time-consuming trick: Instead of downloading all projects at once with a single query, it performs thousands of small queries and puts the responses back together. This works if the queries are chosen in such a way that each project appears at least once in any of the responses, as described below.

The query is defined by the URL and the query-json which is delivered via POST:

```
def api_url(text, pageNumber, pageSize):
    return f"https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA_NONH2020_PROD&text={text}&pageNumber={pageNumber}&pageSize={pageSize}"


query = {
    "bool": {
    }
}

```

The query-URL has three parameters: ```text```, ```pageNumber```, and ```pageSize```.
- ```pageSize``` is set to 100 (maximum)
- ```pageNumber``` will be iterated from 1 to ```total_results // pageSize + 2```, where ```total_results``` is the number of projects in the query, a value that is returned by every successful response. 
- ```text``` is the query search text. It is applied to the description (objective), the title, the id and the program of the project. 

In order to download all projects we use the following trick, which takes advantage of the fact that the query text is also applied to the id of the project. We perform 10000 queries with query text
- ***0000
- ***0001
- ***0002
- ***0003
- ***0004
- ***0005
- ...
- ***9998
- ***9999

Each query will return
- all projects with ids ending on ***XXXX 
- all projects with the number XXXX in their program, description, title etc. This is considered "sidecatch".


Since all projects have an idea ending on one of the 10000 possibilities for the digits XXXX, every project will show up at least once in the queries. The duplicates produced by the sidecatch are later removed in post-processing. The reason to scan the ids by their four last digits XXXX is that by doing it is ensured that almost each query will produce less than 10000 results. The most problematic queries are those where, e.g. XXXX=2020 (because of Horizon 2020 as program name). 




## Manual Data

The ```ManualData``` simply loads data from a csv file which is usually stored in the data folder of the respective topic, e.g. ```in data/quantum/input_manual_projects.csv```, as specified in the workflow settings. In order to add manual data, one needs to open the manual data with a text editor and manually add rows similar to the example below:

```
title;objective;ecMaxContribution;programAbbreviation;id;startDate;endDate;ecSignatureDate;LLMCategory
Euro-Q-Exa;quantum computing infrastructure;12500000;Procurement;61104-2024;2024-09-30;2024-09-30;2024-09-30;quantum computing
EuroQCS-France;quantum computing infrastructure;4187100;Procurement;589009-2024;2024-09-25;2024-09-25;2024-09-25;quantum computing
EuroQCS-Poland;quantum computing infrastructure;6139500;Procurement;422076-2024;2024-06-28;2024-06-28;2024-06-28;quantum computing
Lumi-Q;quantum computing infrastructure;2499900;Procurement;611104-2024;2024-09-25;2024-09-25;2024-09-25;quantum computing
```
