"""Data processing module for project categorization and analysis."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from lxml import etree
import copy
import networkx as nx
import requests
plt.style.use('bmh')
import requests
import json
from tqdm import tqdm
import pickle
import time
import logging
import openai
#from langchain_ollama import OllamaLLM
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def find_all(a_str, sub):
    """Find all occurrences of substring in string."""
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub)

def split(delimiters, string, maxsplit=0):
    """Split string by multiple delimiters."""
    import re
    regex_pattern = '|'.join(map(re.escape, delimiters))
    return re.split(regex_pattern, string, maxsplit)


class DimensionAdder():
    """Base class for adding dimensions to project data."""
    def __init__(self, project_df, orga_df):
        self.project_df = project_df
        self.orga_df = orga_df

class KeywordMatchScorer(DimensionAdder):
    """Score projects based on keyword matches in titles and objectives."""

    def __init__(self, project_df, orga_df, keyword_list):
        """Initialize with project data and scoring keywords."""
        self.project_df = project_df
        self.orga_df = orga_df
        self.keyword_list = keyword_list
        self.match_score = None
        self.match_wordss = None
        logger.info('Keyword Match Score Routine initialized')

    def get_data(self):
        """Return processed project and organization data."""
        logger.info('Return data')
        return self.project_df, self.orga_df
    
    def get_filtered_data(self, threshold):
        """Filter data based on match score threshold."""
        logger.info(f"Apply match score filter to project data")
        project_df = self.project_df.sort_values(by='matchScore')
        topic_threshold = threshold
        topic_project_df = project_df[project_df["matchScore"] > topic_threshold]
        topic_project_df.to_csv('data/funding_and_tenders_projects_filtered.csv', index=False, sep=";")
        logger.info(f" --> There are {len(topic_project_df)} projects left after filtering (out of {len(project_df)})")
        logger.info(f"Apply match score filter to organization data")
        topic_orga_df = self.orga_df[self.orga_df["projectID"].isin(topic_project_df["id"])]
        logger.info(f" --> There are {len(topic_orga_df)} organizations left after filtering (out of {len(self.orga_df)})")
        return topic_project_df, topic_orga_df

    def compute_add_match_score(self):
        """Calculate and add keyword match scores to projects."""
        project_ids = list(self.project_df["id"])
        complete_project_ids = np.asarray(self.project_df["id"])
        complete_project_objectives = np.asarray(self.project_df["objective"])
        complete_project_titles = np.asarray(self.project_df["title"])

        match_scores = []
        match_wordss = []
        matched_project_ids = set()

        logger.info('Start computing match scores based on keyword list')
        for j, project_id in enumerate(project_ids):
                    
            objective, title =complete_project_objectives[j], complete_project_titles[j]
            sentence = str(title) + " " + str(objective) 
            sentence = sentence.lower()
            match_score = 0
            match_words = []
            for word in self.keyword_list:
                if word in sentence:
                        positions = find_all(sentence, word)
                        cpos = 0
                        for pos in positions:
                            cpos+= 1
                            match_score += (1-(pos/float(len(sentence))))
                        matched_project_ids.add(project_id)
                        match_words.append(word)
            #match_score = match_score/len(sentence)
            match_scores.append(match_score)
            match_wordss.append(match_words)
            print(f"{j/float(len(project_ids))*100:.1f}% - Number of matched projects: {len(matched_project_ids)}", end="\r")

        self.match_score = match_scores 
        self.match_words = match_wordss

        logger.info('Add match scores to dataset')
        self.project_df['matchScore'] = match_scores 
        self.project_df['matchWords'] = match_wordss

    def plot_matchscore_histogram(self, filename):
        """Generate histogram of project match scores."""
        logger.info('Generate match score histogram')
        plt.figure(figsize=(15,5))
        bbins = np.linspace(0.0, 20, 100)
        plt.hist(self.project_df["matchScore"], bins=bbins,rwidth=0.8, edgecolor="#2b8cbe", color="#a6bddb",  label="All projects")
        #plt.hist(sorted_project_df.loc[sorted_project_df["hierarchy_lvl3"] == "CNECT/C"]["matchScore"], edgecolor="#b10026", color="#e31a1c", bins= bbins,rwidth=0.85, alpha=1,label="CNECT projects")
        #plt.hist(self.project_df_c2["matchScore"], bins=bbins, rwidth=0.85, edgecolor="#fe9929", color="#fee391", alpha=1, label="C2 Projects")
        plt.gca().set_yscale('log')
        plt.legend()
        plt.xlabel("Match Score")
        plt.ylabel("Number of Projects")
        plt.savefig(filename)



class LLMCategorizer(DimensionAdder):
    """Categorize projects using LLM-based analysis."""

    def __init__(self, project_df, orga_df, prompt_instruction):
        """Initialize with data and LLM prompt template."""
        self.project_df = project_df
        self.orga_df = orga_df
        self.prompt_instruction = prompt_instruction
        self.api_key = None
        self.match_wordss = None
        logger.info('LLM Categorization scheme routine initialized')

    def get_prompt(self, desc):
        """Generate LLM prompt from project description."""
        return self.prompt_instruction + '      "' + desc + '"'

    def get_data(self):
        """Return categorized project and organization data."""
        logger.info('Return data')
        return self.project_df, self.orga_df
    

    def categorize(self, model_location="local"):
        """Categorize projects using LLM."""
        response_json_list = []
        for project_id, project_acronym, project_desc, project_kw in zip(
            self.project_df["id"],
            self.project_df["acronym"],
            self.project_df["objective"], 
            self.project_df["matchWords"]
        ):
            logger.info(f'Generate response for project id {project_id} acronym {project_acronym} (Keywords: {project_kw})')
            prompt = self.get_prompt(project_desc)
            
            if model_location == "local":
                #llm = OllamaLLM(model="Meta-Llama-3.3-70B-Instruct")
                response = llm.invoke(prompt)
            else:
                response = make_chat_completion(
                    prompt=prompt,
                    model=os.getenv("lite_llm_model"),
                    api_key=os.getenv("lite_llm_api_key"),
                    base_url=os.getenv("lite_llm_url")
                )
            logger.info(f'    ---> Response: {response}')
            response_json_list.append(response)

        logger.info('Add categories to dataset')
        self.project_df['LLMCategory'] = response_json_list

def make_chat_completion(
    prompt: str,
    model: str = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_retries: int = 3,
    base_delay: float = 1,
    delay_multiplier: float = 3
) -> str:
    """Make a chat completion request with retry logic."""
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            # Print response details for debugging
            print("Response model:", response.model)
            return response.choices[0].message.content if response.choices else ""
        except openai.OpenAIError as e:
            # If this was the last attempt, log the final error and return
            if attempt >= max_retries:
                print(f"Final error in chat completion after {attempt+1} attempts: {e}")
                return ""
            
            # Calculate delay using base_delay and delay_multiplier
            delay = base_delay * (delay_multiplier ** attempt)
            
            # Otherwise, wait and retry
            print(f"Error in chat completion (attempt {attempt+1}/{max_retries+1}): {e}")
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
