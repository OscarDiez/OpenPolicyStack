import logging
from data_sourcing import FundingAndTenderPortal, ManualData
from data_processing import KeywordMatchScorer, LLMCategorizer
from data_evaluation import OrganizationsByCountryGroupOverTime
from data_delivering import TeamsDeliverer
from data_utils import *

import pandas as pd 
import json
from datetime import datetime, timedelta
import sqlite3
import shutil
from workflow_settings import sourcing_settings
import os

logger = logging.getLogger(__name__)







class Workflow():
    def __init__(self, name, settings_class):
        self.name = name
        self.settings = settings_class

class DataSourcingWorkflow(Workflow):
    def __init__(self, name, settings_class):
        super().__init__(name, settings_class)

    def run(self):
        data_source_ft = FundingAndTenderPortal(self.settings.raw_projects_filename, self.settings.raw_organizations_filename)
        data_source_ft.update_source(suppress_crawl=self.settings.suppress_ft_crawl)
    



class MonitorWorkflow(Workflow):
    def __init__(self, name, settings_class):
        super().__init__(name, settings_class)
        
    def run(self):



        metadata = dict()
        metadata["DataAnalysisStartDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        

        if not self.settings.suppress_llm_categorization:
            data_source_ft = FundingAndTenderPortal(sourcing_settings.raw_projects_filename, sourcing_settings.raw_organizations_filename)
            project_df, orga_df = data_source_ft.load_saved_data()


            match_scorer = KeywordMatchScorer(project_df, orga_df, self.settings.keyword_list)
            match_scorer.compute_add_match_score()
            match_scorer.plot_matchscore_histogram(self.settings.matchscore_histogram_filename)
            project_df, orga_df = match_scorer.get_filtered_data(self.settings.match_score_threshold)
            


            llm_categorizer = LLMCategorizer(project_df, orga_df, self.settings.prompt_instruction)
            llm_categorizer.categorize(model_location=self.settings.llm_location)
            project_df, orga_df = llm_categorizer.get_data()


            project_df.to_csv(self.settings.filtered_projects_filename, index=False, sep=";")
            orga_df.to_csv(self.settings.filtered_organizations_filename, index=False, sep=";")

        #Load new and old data
        project_df = pd.read_csv(self.settings.filtered_projects_filename, delimiter=";")
        orga_df = pd.read_csv(self.settings.filtered_organizations_filename, delimiter=";")
        try:
            project_df_prev = pd.read_csv(self.settings.filtered_prev_projects_filename, delimiter=";")
        except FileNotFoundError as e:
            project_df_prev = project_df
            
    
        if self.settings.import_manual_data:
            data_source_manual = ManualData()
            project_df_manual, orga_df_manual = data_source_manual.load_saved_data(self.settings.manual_project_data_filename, self.settings.manual_orga_data_filename)
            # Ensure columns are in the same order before concatenation
            project_df_manual = project_df_manual.reindex(columns=project_df.columns, fill_value="")
            orga_df_manual = orga_df_manual.reindex(columns=orga_df.columns, fill_value="")
            project_df = pd.concat([project_df, project_df_manual], ignore_index=True, sort=False)
            project_df_prev = pd.concat([project_df_prev, project_df_manual], ignore_index=True, sort=False)
            orga_df = pd.concat([orga_df, orga_df_manual], ignore_index=True, sort=False)



        project_df = split_raw_category(project_df,3,"LLMCategory")
        project_df_prev = split_raw_category(project_df_prev,3,"LLMCategory")      

        project_df = remap_dimension(project_df, "LLMCategory1","LLMSubCategory", self.settings.sub_mapping_dict)
        project_df_prev = remap_dimension(project_df_prev, "LLMCategory1", "LLMSubCategory",self.settings.sub_mapping_dict)
        project_df = remap_dimension(project_df, "LLMCategory2","LLM_TRL", self.settings.trl_mapping_dict)
        project_df_prev = remap_dimension(project_df_prev, "LLMCategory2", "LLM_TRL",self.settings.trl_mapping_dict)

        # Throw out irrelevant projects
        project_df = remap_dimension(project_df, "LLMCategory0", "LLMCategory",self.settings.mapping_dict)
        project_df, orga_df = strip_by_dimension(project_df, orga_df, "LLMCategory", "nan")
        project_df_prev = remap_dimension(project_df_prev, "LLMCategory0", "LLMCategory",self.settings.mapping_dict)
        project_df_prev, __ = strip_by_dimension(project_df_prev, orga_df, "LLMCategory", "nan")


        #Compare new with previous data and create a new dataframe containing all new projects
        new_projects = project_df[~project_df["id"].isin(project_df_prev["id"])]
        #remove projects from new_projects with a startDate older than 2 weeks
        # Ensure 'ecSignatureDate' is converted to timezone-aware datetime
        new_projects['ecSignatureDate'] = pd.to_datetime(new_projects['ecSignatureDate'], utc=True, errors='coerce')

        # Calculate the timestamp for 4 weeks ago, with UTC timezone
        four_weeks_ago = pd.Timestamp.now(tz='UTC') - timedelta(weeks=4)

        # Filter the DataFrame with the corrected comparison
        new_projects = new_projects[new_projects['ecSignatureDate'] > four_weeks_ago]
        new_projects.to_csv(self.settings.processed_diff_projects_filename, index=False, sep=";")


        current_year = datetime.now().year
        print(current_year)

        #not sure if the block below is needed as the same is already done in the sourcing class....
        project_df['startDate'] = pd.to_datetime(project_df['startDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['endDate'] = pd.to_datetime(project_df['endDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['ecSignatureDate'] = pd.to_datetime(project_df['ecSignatureDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['ecSignatureDate'] = pd.to_datetime(orga_df['ecSignatureDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['startDate'] = pd.to_datetime(orga_df['startDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['endDate'] = pd.to_datetime(orga_df['endDate'], format='mixed', utc=True, errors = 'coerce')


        print(project_df.columns)
        project_df = project_df.drop(columns=['subTypeOfAction', 'language', 'deliverables', 'esST_checksum', 'esST_FileName', 'DATASOURCE', 
                                              'REFERENCE', 'subProgramme', 'participants',
                                              'es_ContentType', 'esST_URL','publications', 'typeOfMGAs', 'pics', 'typeOfActions', 'countries',
                                              'projectObjective', 'publicationsAvailable', 'legalEntityNames', 'programmeDivision', 'cenTagsA', 
                                              'cenTagsB',
                                              'destinationGroup', 'mission', 'destination', 'missionGroup',
                                              'LLMCategory0','LLMCategory1','LLMCategory2'])
        orga_df = orga_df.drop(columns=['organizationType', 'website'])
        print(project_df.columns)
        #export project_df and orga_df as sqlite databases using sqlalchemy which can then be accessed by metabase
        metadata["DataAnalysisEndDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        metadata["categorization_prompt"] = self.settings.prompt_instruction
        metadata["keyword_list"] = ",".join(self.settings.keyword_list)
        metadata["matchscore_threshold"] = self.settings.match_score_threshold
        metadata_df = pd.DataFrame([metadata])
        conn_db = sqlite3.connect(self.settings.db_filename)
        project_df.to_sql('projects', conn_db, if_exists='replace')
        orga_df.to_sql('organizations', conn_db, if_exists='replace')
        metadata_df.to_sql('metadata', conn_db, if_exists='replace')




        for evaluation_name, evaluation_class in self.settings.evaluations.items():
            evaluation = evaluation_class(project_df, orga_df)
            evaluation.evaluate(2015, current_year)
            evaluation.plot_result(f"deliverables/{self.name}/{evaluation_name}.png")
            json_string = json.dumps(evaluation.result, indent=4)
            with open(f"deliverables/{self.name}/{evaluation_name}.json", 'w') as f:
                json.dump(evaluation.result, f)

        evaluation_name = "OrganizationsByCountryGroupOverTime"
        evaluation = OrganizationsByCountryGroupOverTime(project_df, orga_df)
        evaluation.evaluate(2015, current_year, fraction=False)
        json_string = json.dumps(evaluation.result, indent=4)
        with open(f"deliverables/{self.name}/{evaluation_name}_absolute.json", 'w') as f:
            json.dump(evaluation.result, f)


        ################# DELIVERY OF THE DELIVERABLES ########################
        if self.settings.send_deliverable == True:
            zip_filename = zip_files_in_folder(f"deliverables/{self.name}", f"deliverables/{self.name}/deliverables")
            #deliverer = GMailDeliverer(self.settings.deliverable_email_settings["sender"], self.settings.deliverable_email_settings["recipients"], self.settings.deliverable_email_settings["subject"], self.settings.deliverable_email_settings["message"], attachment_filename=f"{zip_filename}")
            #deliverer.send_mail()
            # GMAIL not allowed
        
        ################# Quantum newsletter ########################
        #create a string listing the projects in new_projects with title acronym, id and description in a humad-readable newsletter-style way
        
        number_new_projects = len(new_projects)

        if (number_new_projects > 0) and (number_new_projects < 20) and self.settings.send_newsletter == True:
            newsletter = """

NEW PROJECTS IN THE DATABASE

            """

            for index, row in new_projects.iterrows():
                newsletter += f"\n\n\nTitle: {row['title']}\n\nSignature Date: {row['ecSignatureDate']}\n\nStart Date: {row['startDate']}\nAcronym: {row['acronym']}\nURL: {row['url']}\n\n{row['objective']}\n\n"

            print(newsletter)
            newsletter += """
            

This is an automated message generated by EFMO, the European Funding Monitor. If you would like to unsubscribe, please contact Schmidt Ludovic or Doru Tanasa.
            """
            # GMAIL DELIVERY - DEPRECATED
            #newsletter_deliverer = GMailDeliverer(self.settings.newsletter_email_settings["sender"],
                                            #self.settings.newsletter_email_settings["recipients"], 
                                            #self.settings.newsletter_email_settings["subject"], 
                                            #newsletter)
            #newsletter_deliverer.send_mail()
            
            # TEAMS DELIVERY
            teams_deliverer = TeamsDeliverer(self.settings.newsletter_email_settings["sender"],
                                            os.getenv("hook_teams"),
                                            self.settings.newsletter_email_settings["subject"], 
                                            newsletter)
            teams_deliverer.send_message()
            
        ################# Set downloaded data as new ########################
        #Delete old project and orga data and Rename new project and orga file such that it becomes the old one
        shutil.copy(self.settings.filtered_projects_filename, self.settings.filtered_prev_projects_filename)
        logger.info(f"WORKFLOW COMPLETED")
