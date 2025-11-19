# EFMO Data Flow ("Backend")


## Overview

The data flow consist of these steps:
- [Data Sourcing](data_sourcing.md)
- [Data Processing](data_processing.md)
- [Data Evaluation](data_evaluation.md)
- [Data Delivering](data_delivering.md)

These steps can be organized in workflows, controlled by the workflow settings. 

The workflow execution is triggered by the [scheduler](scheduler.md).




## Funding Monitoring Workflows

The funding monitor for a specific topic consists of two workflows defined in ```data_workflows.py```:
- The sourcing workflow which downloads the entire raw data from the funding and tender portal (see [here](data_sourcing.md)). This workflow takes several hours.
- The processing+evaluation+delivery workflow for quantum technologies which performs the filtering and the catergorization of the raw data plus the distribution of the processed data. This workflow takes several hours. 

Both workflows are defined in the ```data_workflows.py``` file with settings stored in the ```workflow_settings.py``` file They are scheduled for execution in the ```scheduler.py``` file. 


### Sourcing workflow

The sourcing workflow defined by ```DataSourcingWorkflow(Workflow)``` in the ```data_worflows.py``` file simply calls the methods of the ```FundingAndTenderPortal``` dats sourcing class in the ```data_sourcing.py``` file, see [here](data_sourcing.md) for more details. This workflows has three parameters saved in the ```sourcing_settings``` class of the workflow settings in ```workflow_settings.py```:
- ```suppress_ft_crawl```: Boolean which decides whether the new data is pulled from the API. By default this is false. One may set it to True when debugging the code such that the hour-long process is not triggered every time. 
- ```raw_projects_filename```: Filename for the raw project data
- ```raw_organizations_filename```: Filename for the raw organizations data

The crawled data is temporarily stored as ```projects_tmp.dat``` and ```orgas_tmp.dat``` in the root folder. At the end of the sourcing workflow the raw data is saved in csv format to ```raw_projects_filename``` and ```raw_organizations_filename```.


### Processing+Evaluation+Delivery workflow

This workflow, defined by the ```run```-method in the ```MonitorWorkflow(Workflow)``` class, performs a long sequence of steps:

#### 1. Keyword Scoring

Project and organization data is loaded from ```raw_projects_filename``` and ```raw_organizations_filename```. Then the ```KeywordMatchScorer``` (see [Data Processing](data_processing.md)) is used to assign a match score to each project and filter out all projects with a match score below a certain threshold. The parameters in the ```workflow_settings.py``` file are:
- ```keyword_list```: List of keywords for the match score analysis
- ```matchscore_histogram_filename```: filename for storing the histogram plot (see [Data Processing](data_processing.md))
- ```match_score_threshold```: Only keep projects with a match score exceeding this threshold

Note that this section is only executed if ```suppress_llm_categorization``` in the workflow settings is False.


#### 2. LLM Categorization

The ```LLMCategorizer``` (see [Data Processing](data_processing.md)) is used to assign categories to all projects which have survived the keyword filter. The processed data with the LLM output is then saved in a separate csv file. The parameters in the ```workflow_settings.py``` file are:
- ```prompt_instruction```: Instructions provided to the LLM (together with the description of the project)
- ```llm_location```: can be ```local``` or ```remote```, see [Data Processing](data_processing.md) for details. 
- ```filtered_projects_filename```: Filename for storing the processed project data with the LLM output as an additional column
- ```filtered_organizations_filename```: Filename for storing the processed organizations data belonging to the processed projects

Note that this section is only executed if ```suppress_llm_categorization``` in the workflow settings is False.

#### 3. Adding manual data

Next, the filtered data that was just saved is loaded again and manual data is added using the ```ManualData``` class from ```data_sourcing.py```. The workflow parameters are:
- ```manual_project_data_filename```: filename containing the manual project data (see [Data Sourcing](data_sourcing.md) for more info)
- ```manual_orga_data_filename```: filename containing the manual organizations data (see [Data Sourcing](data_sourcing.md) for more info)

This section is only executed if ```import_manual_data``` is set to True. 


#### 4. Processing LLM Outputs

Next, the raw LLM Output, so far stored in the "LLMCategory" column of the project dataset is processed using auxiliary methods defined in ```data_utils.py```. 

For example, in the quantum workflow, we ask the LLM to provide us the pillar of quantum technologies, the platform and teh TRL level of the project separated by commas. So for each project we get output similar to this one:

```quantum computing, neutral atoms, 6```

In this part of the workflow, the output is split and the three types of information are assigned to separate columns ("LLMCategory", "LLmSubCategory", "LLM TRL") rather than a single column.

At the same time, the category names are cleaned up. The ourput of the LLM may be "quantum computation" even though we asked it whether the project is part of "quantum computing. Thus, as long as the output contains "quantum comput", the project will be assigned to category "quantum computing" in post-processing. This is done based on dictionary mappings defined in the workflow settings. For example, for the main category of quantum technologies, the mapping dictionary looks like this:

```
mapping_dict = {
        "quantum comp": "quantum computing",
        "quantum communication": "quantum communication",
        "quantum sensing": "quantum sensing",
        "basic": "basic science"
    }
```

If non of the keys of teh dictionary if found in the LLM output, the category is corrected to "nan" and the project is removed (method ```strip_by_dimension```)

The parameters in the workflow settings for this section are:
- ```mapping_dict```: Mapping dictionary for the first categorization
- ```sub_mapping_dict```: Mapping dictionary for the second categorization
- ```trl_mapping_dict```: Mapping dictionary for the third (TRL) categorization


In addition, the project dataset after the filtering is compared with that of the previous workflow run and the difference is stored in ```processed_diff_projects_filename```. 


#### 5. Database creation (for metabase)

Next, some column in the project and the organizations dataset are renamed for more clarity. 
Further, some columns are removed because they are either duplicated or irrelevant and would just clutter the dataset. The cleaned up data is then saved in an SQLite database for the purpose of making the data available in the metabase dashboard.

The parameters in the workflow settings for this section are:
- ```db_filename```: filename of the SQLite database


#### 6. Evaluations

Next, the evaluations are triggered which produce the deliverables (such as json files and plots in the ```deliverables``` folder). The evaluations to be executed are defined in the ```evaluations``` dictionary of the workflow settings. 

#### 7. Delivery of deliverables

There are two possible deliveries implemented at the moment:
- if ```send_deliverable``` in the workflow settings is set to True, all files in the deliverables folder of the topic are zipped. Then, the zip file is sent out via email, with email steeing specified in ```deliverable_email_settings``` of the workflow settings. 
- if ```send_newsletter``` in the wokflow settings is set to True, EFMO sends out a list of recently added projects (compared to the last run of the workflow) via email, with email settings specified in ```newsletter_email_settings``` of the workflow settings. 

Finally, the csv files containing the processed project and organizations are re-organized, such that the next workflow run can detect the projects which have been newly added. 









