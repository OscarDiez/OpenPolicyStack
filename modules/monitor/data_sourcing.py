"""Data sourcing module for EC project data retrieval and processing."""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from lxml import etree
import copy
import networkx as nx
import requests
import requests
import json
from tqdm import tqdm
import pickle
import yaml
import logging
import time
from datetime import datetime
import sqlite3
logger = logging.getLogger(__name__)

class DataSource:
    """Base class for data sources."""
    def __init__(self):
        pass


class FundingAndTenderPortal(DataSource):
    """Handles data retrieval from EU Funding & Tenders Portal."""
    
    def __init__(self, raw_project_data_filename, raw_orga_data_filename):
        """Initialize with paths for project and organization data storage."""
        self.raw_project_data_filename = raw_project_data_filename
        self.raw_orga_data_filename = raw_orga_data_filename
        logger.info('F&T Data sourcer initialized')

    @staticmethod
    def _get_api_url(text: str, page_number: int, page_size: int) -> str:
        """Generate the API URL for the EU funding and tender portal.
        
        swagger: https://api.tech.ec.europa.eu/search-api/prod/swagger-ui/index.html
        Args:
            text: Search text
            page_number: Page number for pagination
            page_size: Number of items per page
        """
        api_key = os.getenv('SEDIA_API_KEY', '???????')
        return f"https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey={api_key}&text={text}&pageNumber={page_number}&pageSize={page_size}"

    def update_source(self, suppress_crawl=False):
        """Update data by crawling F&T portal or loading from cache if suppressed."""
        logger.info('Select F&T portal as data source')
        project_df, orga_df = self.crawl_funding_and_tenders_portal(suppress_crawl=suppress_crawl)
        return project_df, orga_df

    def load_saved_data(self):
        """Load previously saved project and organization data from pickle files."""
        logger.info('Load saved F&T data')
        project_df = pd.read_pickle(self.raw_project_data_filename)
        organization_df = pd.read_pickle(self.raw_orga_data_filename)
        logger.info('Finished saved F&T data')
        return project_df, organization_df


    def crawl_funding_and_tenders_portal(self, suppress_crawl):
        """Crawl F&T portal API for project data or load from cache if suppressed.
        
        Args:
            suppress_crawl: If True, load from cache instead of crawling

        Returns:
            tuple: (project_dataframe, organization_dataframe)
        """
        metadata = dict()
        metadata["SourcingStartDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not suppress_crawl:
        
            logger.info('Begin systematic crawl by project id')
            pdfsnew = []
            odfsnew = []

            codes = np.arange(1,10000)


            for code in codes:
                text = "***" + f"{code:04}"
                logger.info(f'Initiate download for {text}')

                pageNumber = 1
                pageSize = 100
                
                query = {
                "bool": {
                }
                }

                attempts = 0
                successful = False
                while not successful:
                    attempts += 1
                    if attempts > 5:
                        logger.error(f'{text}: Skip {text}')
                        break
                    try:
                        response = requests.post(self._get_api_url(text, pageNumber, pageSize), json=query)
                        out = response.json()
                        total_results = out['totalResults']
                        successful = True
                    except requests.exceptions.ConnectionError:
                        logger.error(f'{text}: ConnectionError. Overview download failed for  {text} on attempt {attempts}. Will try again in 30s.')
                        time.sleep(30)
                    except requests.exceptions.JSONDecodeError:
                        logger.error(f'{text}: JSONDecodeError. JSON Decoding failed for overview download for {text} on attempt {attempts}. Will try to redownloads in 30s.')
                        time.sleep(30)
                    except:
                        logger.error(f'{text}: Unknown error for overview download for {text} on attempt {attempts}. Will try to redownloads in 30s.')
                        time.sleep(30)

                if total_results < 1: 
                    continue
                    print(text, "skipped")
                
                
                jsons = []
                
                for pageNumber in np.arange(1, total_results // pageSize + 2):

                    successful = False
                    logger.info(f'{text}: Download page {pageNumber}')
                    #print(pageNumber, "/", total_results // pageSize + 1)
                    attempts = 0
                    while not successful:
                        attempts += 1
                        if attempts > 5:
                            logger.error(f'{text}: Skip page {pageNumber}')
                        try:
                            response = requests.post(self._get_api_url(text, pageNumber, pageSize), json=query)
                            jsons.append(response.json())
                            successful = True
                        except requests.exceptions.ConnectionError:
                            logger.error(f'{text}: ConnectionError. Download failed for page {pageNumber} on attempt {attempts}. Will try again in 5s.')
                            time.sleep(5)
                        except requests.exceptions.JSONDecodeError:
                            logger.error(f'{text}: JSONDecodeError. JSON Decoding failed for page {pageNumber} on attempt {attempts}. Will try to redownloads in 5s.')
                            time.sleep(5)

                
                ###############################################
                
                
                rawdatas = []
                rawdatas_orga = []

                logger.info(f'{text}: Read pages and extract data')
                
                for j, jsond in enumerate(jsons):
                    results = jsond["results"]
                    for result in results:
                        rawdata = copy.deepcopy(result["metadata"])
                        for key, value in rawdata.items():
                            try:
                                rawdata[key] = value[0]
                            except:
                                rawdata[key] = value

                        if rawdata["projectId"][-4:None] == f"{code:04}":
                            rawdatas.append(rawdata)
                            
                            try:
                                organizations = rawdata["participants"][0]
                                organizations = json.loads(organizations)
                                for organization in organizations:
                                    organization["projectID"] = rawdata["projectId"]
                                    rawdatas_orga.append(copy.deepcopy(organization))
                            except: 
                                organizations = rawdata["participants"]
                                organizations = json.loads(organizations)
                                for organization in organizations:
                                    organization["projectID"] = rawdata["projectId"]
                                    rawdatas_orga.append(copy.deepcopy(organization))
                                
                
                part_project_df = pd.DataFrame.from_dict(rawdatas, orient='columns')
                part_orga_df = pd.DataFrame.from_dict(rawdatas_orga, orient='columns')
                pdfsnew.append(part_project_df)
                odfsnew.append(part_orga_df)

                logger.info(f'{text}: Data extraction finished: #Results:, {total_results},  #Projects:, {len(rawdatas)}, #Orgas:, {len(rawdatas_orga)}')



            logger.info(f'Save data as pickle file')
            with open("projects_tmp.dat", "wb") as fp:   #Pickling
                pickle.dump(pdfsnew, fp)
                
            with open("orgas_tmp.dat", "wb") as fp:   #Pickling
                pickle.dump(odfsnew, fp)

        if suppress_crawl == True:
            file = open("projects_tmp.dat",'rb') #TODO: Triggers memory error, possibly remove
            pdfsnew = pickle.load(file)
            file = open("orgas_tmp.dat",'rb')
            odfsnew = pickle.load(file)
        

        project_df = pd.concat(pdfsnew)
        orga_df = pd.concat(odfsnew)


        logger.info(f'Rename and reformat dimensions in project data')
        project_df.rename(columns={'euContributionAmount': 'ecMaxContribution'}, inplace=True)
        project_df.rename(columns={'projectId': 'id'}, inplace=True)
        #project_df.rename(columns={'topicAbbreviation': 'topicId'}, inplace=True)
        project_df.rename(columns={'frameworkProgramme': 'programAbbreviation'}, inplace=True)
        project_df['startDate'] = pd.to_datetime(project_df['startDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['endDate'] = pd.to_datetime(project_df['endDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['ecSignatureDate'] = pd.to_datetime(project_df['ecSignatureDate'], format='mixed', utc=True, errors = 'coerce')
        
        
        new_eccontribs = list()
        for j, val in enumerate(project_df['ecMaxContribution']):
            try:
                new_eccontribs.append(float(val))
            except:
                new_eccontribs.append(0)
        project_df['ecMaxContribution'] = new_eccontribs


        logger.info(f'Enrich organization data using project data')
        countries = []
        for k, orga_row in enumerate(orga_df["postalAddress"]):
            #country = yaml.load(orga_row.replace("None", '\"nan\"'), yaml.SafeLoader)["countryCode"]["abbreviation"]
            country = orga_row["countryCode"]["abbreviation"]
            countries.append(country)
        ## EC Signature date
        signaturedates = []
        startdates = []
        enddates = []
        acronyms = []
        hierarchylevel2s = []
        lastpid =0
        for k, pid in enumerate(orga_df["projectID"]):
            if k % 10000 == 0: 
                logger.info(f'  {k} out of {len(orga_df["projectID"])} organizations enriched')
            if lastpid != pid: pid_proj_df = project_df[project_df["id"] == pid] #this accelerates the process by a factor of approx 10, since the number of pid filtering processes is minimized.
            lastpid = pid
            signaturedates.append( pid_proj_df["ecSignatureDate"].values[0])
            startdates.append( pid_proj_df["startDate"].values[0])
            enddates.append( pid_proj_df["endDate"].values[0])

            hierarchylevel2s.append( pid_proj_df["programAbbreviation"].values[0])
            acronyms.append( pid_proj_df["acronym"].values[0])

        logger.info(f'Rename dimensions in organization data')

        orga_df["ecSignatureDate"] = signaturedates
        orga_df["startDate"] = startdates
        orga_df["endDate"] = enddates
        orga_df["programAbbreviation"] = hierarchylevel2s
        orga_df["acronym"] = acronyms
        orga_df["country"] = countries
        
        orga_df.rename(columns={'eucontribution': 'ecMaxContribution'}, inplace=True)
        orga_df['latitude'] = pd.to_numeric(orga_df['latitude'], errors="coerce")
        orga_df['longitude'] = pd.to_numeric(orga_df['longitude'], errors="coerce")
        
        
        logger.info(f'Save data as dataframe')
        project_df.to_pickle(self.raw_project_data_filename)
        orga_df.to_pickle(self.raw_orga_data_filename)
        
        #################

        
        project_df = project_df.drop(columns=['subTypeOfAction', 'language', 'deliverables', 'esST_checksum', 'esST_FileName', 'DATASOURCE', 
                                              'REFERENCE', 'subProgramme', 'participants',
                                              'es_ContentType', 'esST_URL','publications', 'typeOfMGAs', 'pics', 'typeOfActions', 'countries',
                                              'projectObjective', 'publicationsAvailable', 'legalEntityNames', 'programmeDivision', 'cenTagsA', 
                                              'cenTagsB',
                                              'destinationGroup', 'mission', 'destination', 'missionGroup'])
        orga_df = orga_df.drop(columns=['organizationType', 'website'])
        
        project_df = project_df.astype(str)
        orga_df = orga_df.astype(str)
        orga_df['latitude'] = pd.to_numeric(orga_df['latitude'], errors="coerce")
        orga_df['longitude'] = pd.to_numeric(orga_df['longitude'], errors="coerce") 
        project_df['ecMaxContribution'] = pd.to_numeric(project_df['ecMaxContribution'], errors="coerce")
        orga_df['ecMaxContribution'] = pd.to_numeric(orga_df['ecMaxContribution'], errors="coerce")
        project_df['startDate'] = pd.to_datetime(project_df['startDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['endDate'] = pd.to_datetime(project_df['endDate'], format='mixed', utc=True, errors = 'coerce')
        project_df['ecSignatureDate'] = pd.to_datetime(project_df['ecSignatureDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['startDate'] = pd.to_datetime(orga_df['startDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['endDate'] = pd.to_datetime(orga_df['endDate'], format='mixed', utc=True, errors = 'coerce')
        orga_df['ecSignatureDate'] = pd.to_datetime(orga_df['ecSignatureDate'], format='mixed', utc=True, errors = 'coerce')
        print(project_df.columns)
        
        logger.info(f'Save data as database:')
        metadata["SourcingEndDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        metadata_df = pd.DataFrame([metadata])
        conn_db = sqlite3.connect("deliverables/ft_portal_raw.db")
        logger.info(f'Add projects...')
        project_df.to_sql('projects', conn_db, if_exists='replace')
        logger.info(f'Add orgas...')
        orga_df.to_sql('organizations', conn_db, if_exists='replace')
        logger.info(f'Add metadata...')
        metadata_df.to_sql('metadata', conn_db, if_exists='replace')
        logger.info(f'Completed.')
        

        return project_df, orga_df
    



class ManualData(DataSource):
    """Handles manually provided project data in CSV format."""
    
    def __init__(self):
        logger.info('Manual Data sourcer initialized')

    def load_saved_data(self, manual_project_data_filename, manual_orga_data_filename):
        """Load project and organization data from CSV files with semicolon delimiter."""
        logger.info(f'Load manual data from {manual_project_data_filename} and {manual_orga_data_filename}')
        project_df = pd.read_csv(manual_project_data_filename, delimiter=";")
        orga_df = pd.read_csv(manual_orga_data_filename, delimiter=";")
        return project_df, orga_df
