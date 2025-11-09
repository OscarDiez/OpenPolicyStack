import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import datetime
import os
from lxml import etree
import copy
import networkx as nx
import requests
import json
from tqdm import tqdm
import pickle
import logging
import matplotlib.ticker as ticker
import textwrap
plt.style.use('default')
plt.rc('axes',edgecolor='#6d6d6d')
mpl.rcParams['text.color'] = '#6d6d6d'
mpl.rcParams['axes.labelcolor'] = '#6d6d6d'
logger = logging.getLogger(__name__)



def create_year_list(start_year, end_year): 
        years_int = np.arange(start_year, end_year +1)
        years_str  = []
        for year in years_int:
            years_str.append(str(int(float(year))))
        
        return years_str


class Evaluation():
    def __init__(self, project_df, orga_df):
        self.project_df = project_df
        self.orga_df = orga_df
        self.result = None
        logging.info('Evaluation initialized')

    def get_result(self):
        logging.info('Return evaluation result')
        return self.result


class TotalFundingByFPOverTime(Evaluation):

    def evaluate(self, start_year, end_year):
        xyears = create_year_list(start_year, end_year)
        self.xyears = xyears
        fund_dat = dict()
        for agency in np.unique(np.asarray(self.project_df["programAbbreviation"])):
            year_dict = copy.deepcopy(dict.fromkeys(self.xyears,0))
            topic_project_df_filtered_filtered = self.project_df
            topic_project_df_filtered_filtered = topic_project_df_filtered_filtered[topic_project_df_filtered_filtered["programAbbreviation"] == agency]
            query = topic_project_df_filtered_filtered["ecMaxContribution"].groupby(topic_project_df_filtered_filtered["ecSignatureDate"].dt.year).sum()
            
            for key, value in dict(query).items():
                yr = str(int(float(key)))
                if yr in year_dict.keys():
                    year_dict[yr] = float(value)
            fund_dat[agency]  = year_dict

        self.result = fund_dat
        return fund_dat
    
    def plot_result(self, filename):
        plot_colors = ["#FFA07A", "#353867", "#20B2AA", "#31ffca", "#ff9631", "#e43184","#7B68EE", "#4682B4"]*100
        plt.figure(figsize=(6,4))

        bottoms = np.zeros(len(self.xyears))
        color_index=0
        xlabels = self.xyears
        xlabels[-1] = xlabels[-1] + "*"
        for progency, funding in self.result.items():
            values = np.asarray([float(x) for x in list(funding.values())])/1e9
            plt.bar(xlabels, values, bottom = bottoms, label=progency, color = plot_colors[color_index], edgecolor="white")
            bottoms = np.asarray(bottoms) + np.asarray(values)
            color_index+=1
        plt.xticks(rotation=45, ha='right')
        plt.gca().tick_params(colors='#6d6d6d', which='both')
        plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
        plt.legend(frameon=False, loc="upper left", fontsize=8)
        #plt.xlabel("Year")
        #plt.ylim(0,0.8)
        plt.ylabel("Funding (bn EUR)")

        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Source: Funded projects in the eGrants database of the European Commission. All projects are assigned to the year in which the corresponding grant was signed, even if their duration is multiple years. Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        x = list(range(len(self.xyears)))
        plt.text(-1, -0.18, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=250)


class TotalFundingByLLMCategoryOverTime(Evaluation):

    def evaluate(self, start_year, end_year):
        self.xyears = create_year_list(start_year, end_year)
        fund_dat = dict()
        for agency in np.unique(np.asarray(self.project_df["LLMCategory"])):
            year_dict = copy.deepcopy(dict.fromkeys(self.xyears,0))
            topic_project_df_filtered_filtered = self.project_df
            topic_project_df_filtered_filtered = topic_project_df_filtered_filtered[topic_project_df_filtered_filtered["LLMCategory"] == agency]
            query = topic_project_df_filtered_filtered["ecMaxContribution"].groupby(topic_project_df_filtered_filtered["startDate"].dt.year).sum()
            for key, value in dict(query).items():
                yr = str(int(float(key)))
                if yr in year_dict.keys():
                    year_dict[yr] = float(value)
            fund_dat[agency]  = year_dict

        self.result = fund_dat
        return fund_dat
    
    def plot_result(self, filename):
        plot_colors = ["#4682B4", "#353867", "#ff9631", "#e43184","#31ffca","#7B68EE", "#aaaaaa", "#FF1493"]
        plt.figure(figsize=(6,5.2))
        
        plt.grid(axis='y', color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
        

        bottoms = np.zeros(len(self.xyears))
        color_index=0
        xlabels = self.xyears
        xlabels[-1] = xlabels[-1] + "*"
        for progency, funding in list(self.result.items())[::-1]:
            values = np.asarray([float(x) for x in list(funding.values())])/1e9
            if (progency == "quantum computing"):
                lab = "quantum computing & simulation"
            else:
                lab = progency
            
            plt.bar(xlabels, values, bottom = bottoms, label=lab, color = plot_colors[color_index], edgecolor="white")
            bottoms = np.asarray(bottoms) + np.asarray(values)
            color_index+=1

        plt.xticks(rotation=45, ha='right')
        plt.gca().tick_params(colors='#6d6d6d', which='both')
        plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
        plt.legend(frameon=True, loc="upper left", fontsize=8, facecolor='white')
        #plt.xlabel("Year")
        #plt.ylim(0,0.8)
        plt.ylabel("Funding (bn EUR)")

        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        x = list(range(len(self.xyears)))
        plt.text(-1, -0.1, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=250)


class OrganizationsByCountryGroupOverTime(Evaluation):

    def evaluate(self, start_year, end_year, fraction = True):
        #create new pseudo-country for UK when it was still part of the EU
        self.orga_df.loc[(self.orga_df["ecSignatureDate"].dt.date > datetime.date(2020, 2, 1)) & (self.orga_df["country"] == "UK"), "country"] = "UKnoteu" #create new pseudo-country for UK when it was still part of the EU

        revised_orga_df = pd.DataFrame(columns=self.orga_df.columns)

        #go through each orga in orga_df. for each year lying between startdate and enddate of orga, append orga to revised_orga_df
        rows = []
        for index, row in self.orga_df.iterrows():
            proj_start_year = row["startDate"].year
            proj_end_year = row["endDate"].year
            for year in range(proj_start_year, proj_end_year + 1):
                new_row = row.copy()
                new_row["ecSignatureDate"] = datetime.datetime(year, 1, 1)
                rows.append(new_row)
        revised_orga_df = pd.DataFrame(rows)
        self.orga_df = revised_orga_df
        #self.orga_df.to_csv('data/funding_and_tenders_organizations_alldone_new_revised.csv', index=False, sep=";")
        

        self.xyears = create_year_list(start_year, end_year)
        country_groups = {
            "Widening Countries (EU)": ["BG", "HR", "CY", "CZ", "EE", "EL", "HU", "LV", "LT", "MT", "PL", "PT", "RO", "SK","SI"],
            "Other EU": ["AT", "BE", "DE", "DK","ES", "FI", "FR", "IT", "NL", "SE", "IE","LU", "UK"]
        }

        countries = set(list(self.orga_df["country"]))

        existing_codes = set(country_groups.keys())
        for group in country_groups.values():
            existing_codes.update(group)

        missing_codes = countries - existing_codes
        country_groups["Non-EU"] = list(missing_codes)


        fund_dat = dict()
        for country_group_label, country_group in country_groups.items():
            year_dict = copy.deepcopy(dict.fromkeys(self.xyears,0))
            topic_organization_df_filtered_filtered = self.orga_df[self.orga_df["country"].isin(country_group)]
            query = topic_organization_df_filtered_filtered["ecMaxContribution"].groupby(topic_organization_df_filtered_filtered["ecSignatureDate"].dt.year).count()
            query_total = self.orga_df["ecMaxContribution"].groupby(self.orga_df["ecSignatureDate"].dt.year).count()
            for key, value in dict(query).items():
                yr = str(int(float(key)))
                if yr in year_dict.keys():
                    if fraction:
                        year_dict[str(key)] = float(value)/query_total[key]*100
                    else:
                        year_dict[str(key)] = float(value)
            fund_dat[ country_group_label ]  = year_dict

        self.result = fund_dat
        return fund_dat
    
    def plot_result(self, filename):
        plot_colors = ["#4682B4", "#353867", "#ff9631", "#e43184","#31ffca","#7B68EE"]*100
        plt.figure(figsize=(6,4))

        bottoms = np.zeros(len(self.xyears))
        color_index=0
        xlabels = self.xyears
        xlabels[-1] = xlabels[-1] + "*"
        for progency, funding in list(self.result.items())[::]:
            values = np.asarray([float(x) for x in list(funding.values())])
            plt.bar(xlabels, values, bottom = bottoms, label=progency, color = plot_colors[color_index], edgecolor="white", width=1)
            bottoms = np.asarray(bottoms) + np.asarray(values)
            color_index+=1
        plt.xticks(rotation=45, ha='right')
        plt.gca().tick_params(colors='#6d6d6d', which='both')
        plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f'))
        plt.legend(frameon=False, fontsize=8, ncol=3, bbox_to_anchor=(0.8, 1.12))
        #plt.xlabel("Year")
        plt.xlim(-0.5,len(self.xyears)-0.5 )
        plt.ylim(0,100)
        plt.ylabel("Percentage of Organizations (%)")

        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        plt.text(-1, -22, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=300)
        print(self.orga_df)



class OrganizationTypeByCountryGroupOverTime(Evaluation):

    def evaluate(self, start_year, end_year):
        
        #create new pseudo-country for UK when it was still part of the EU
        self.orga_df.loc[(self.orga_df["ecSignatureDate"].dt.date > datetime.date(2020, 2, 1)) & (self.orga_df["country"] == "UK"), "country"] = "UKnoteu" #create new pseudo-country for UK when it was still part of the EU

        revised_orga_df = pd.DataFrame(columns=self.orga_df.columns)

        #go through each orga in orga_df. for each year lying between startdate and enddate of orga, append orga to revised_orga_df
        rows = []
        for index, row in self.orga_df.iterrows():
            proj_start_year = row["startDate"].year
            proj_end_year = row["endDate"].year
            for year in range(proj_start_year, proj_end_year + 1):
                new_row = row.copy()
                new_row["ecSignatureDate"] = datetime.datetime(year, 1, 1)
                rows.append(new_row)
        revised_orga_df = pd.DataFrame(rows)
        self.orga_df = revised_orga_df

        

        self.xyears = create_year_list(start_year, end_year)
        country_groups = {'Private entities': ['PRC'], 'Public / academic entities': ['HES', 'PUB', 'REC'], 'Unknown': ['nan', 'OTH']}



        fund_dat = dict()
        for country_group_label, country_group in country_groups.items():
            year_dict = copy.deepcopy(dict.fromkeys(self.xyears,0))
            topic_organization_df_filtered_filtered = self.orga_df[self.orga_df["type"].isin(country_group)]
            query = topic_organization_df_filtered_filtered["ecMaxContribution"].groupby(topic_organization_df_filtered_filtered["ecSignatureDate"].dt.year).count()
            query_total = self.orga_df["ecMaxContribution"].groupby(self.orga_df["ecSignatureDate"].dt.year).count()
            for key, value in dict(query).items():
                yr = str(int(float(key)))
                if yr in year_dict.keys():
                    year_dict[str(key)] = float(value)/query_total[key]*100
            fund_dat[ country_group_label ]  = year_dict

        self.result = fund_dat
        return fund_dat
    
    def plot_result(self, filename):
        plot_colors = ["#4682B4", "#353867", "#ff9631", "#e43184","#31ffca","#7B68EE"]
        plt.figure(figsize=(6,4))

        bottoms = np.zeros(len(self.xyears))
        color_index=0
        xlabels = self.xyears
        xlabels[-1] = xlabels[-1] + "*"
        for progency, funding in list(self.result.items())[::]:
            values = np.asarray([float(x) for x in list(funding.values())])
            plt.bar(xlabels, values, bottom = bottoms, label=progency, color = plot_colors[color_index], edgecolor="white", width=1)
            bottoms = np.asarray(bottoms) + np.asarray(values)
            color_index+=1
        plt.xticks(rotation=45, ha='right')
        plt.gca().tick_params(colors='#6d6d6d', which='both')
        plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f'))
        plt.legend(frameon=False, fontsize=8, ncol=3, bbox_to_anchor=(0.8, 1.12))
        #plt.xlabel("Year")
        plt.xlim(-0.5,len(self.xyears)-0.5 )
        plt.ylim(0,100)
        plt.ylabel("Percentage of Organizations (%)")

        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Source: Signed quantum-related grants in the eGrants database of the European Commission. Organizations are assigned to all years falling in the project period. See https://europa.eu/!gQkrKR for a list of widening countries. *Funding data of the current year may be incomplete. Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        plt.text(-1, -22, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=250)
        print(self.orga_df)



class TotalFundingbyFP(Evaluation):

    def create_label(self, val):
        return f"{val*np.sum(np.asarray(list(self.result.values())))/1e6/1e2:.1f} bn €"


    def evaluate(self, start_year, end_year):
    
        pie_data = self.project_df["ecMaxContribution"].groupby(self.project_df["programAbbreviation"]).sum()
        pie_threshold = 1e8
        pie_data_big = pie_data[pie_data>pie_threshold]
        pie_data_small = pie_data[pie_data<=pie_threshold]
        pie_data_big["Other"] = np.sum(pie_data_small)
        self.result = pie_data_big.to_dict()
        return self.result
    
    def plot_result(self, filename):
        plot_colors = ["#4682B4", "#353867", "#ff9631", "#e43184","#31ffca","#7B68EE"]
        plt.figure(figsize=(6,4))

        _, _, autotexts = plt.pie(self.result.values(), labels=self.result.keys(), colors=plot_colors[:len(self.result.keys())], wedgeprops = {"edgecolor": "black"}, autopct=self.create_label)
        for autotext in autotexts:
            autotext.set_color('white')

        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Source: Signed quantum-related grants in the eGrants database of the European Commission starting 2014. Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        plt.text(-1, -22, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=250)


class CountryCollaborationGraph(Evaluation):

    def evaluate(self, start_year, end_year):
    
        
        return self.result
    
    def plot_result(self, filename):
        #Disclaimer caption
        plt.subplots_adjust(bottom=0.25)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        t = f"Source: Signed quantum-related grants in the eGrants database of the European Commission starting 2014. Last update: {timestamp}"
        tt = textwrap.fill(t, width=25.4*4.2)
        plt.text(-1, -22, tt, ha='left', va='top', fontdict={"size": 6});
        plt.savefig(filename, dpi=250)
