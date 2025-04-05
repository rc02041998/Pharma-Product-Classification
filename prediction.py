import os
import requests
import random
import json
import boto3
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import time
from multiprocessing import Pool, cpu_count
from requests.exceptions import SSLError
import streamlit as st


class DrugBanClassifier:
    def __init__(self, region_name='us-east-1'):
        """
        Initialize the DrugBanClassifier with AWS Bedrock for Claude 3.5 Sonnet.
        Designed to work in a SageMaker environment with built-in credentials.

        Parameters:
        - region_name: str, AWS region where Bedrock is available (optional)
        """
        # Model ID for Claude 3.5 Sonnet
        self.model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        
        # User agents to rotate for requests
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        ]
        
        # Reliable sources for drug information in India
        self.reliable_sources = [
            "https://cdsco.gov.in/opencms/opencms/en/Drugs/",
            "https://www.nhp.gov.in/drug-banned-in-india_pg",
            "https://www.medindia.net/drug-price/",
            "https://www.mciindia.org/",
            "https://nlem.nic.in/",
            "https://www.indianpharmacyjournal.org/",
            "https://www.mohfw.gov.in/",
            "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3401704/"
        ]
    
    def search_duckduckgo(self, query, num_results=10):
        """
        Perform a search using DuckDuckGo for the given query.

        Parameters:
        - query: str, the search query
        - num_results: int, number of results to return

        Returns:
        - list of search result URLs
        """
        enhanced_query = f"{query} banned drugs in India"
        encoded_query = quote_plus(enhanced_query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        headers = {'User-Agent': random.choice(self.user_agents)}
        response = requests.get(search_url, headers=headers)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        urls = []
        results = soup.find_all('a', class_='result__url')
        
        for result in results[:num_results]:
            href = result.get('href')
            if href and href.startswith('http'):
                urls.append(href)
            elif href:
                base_url = 'https://' + result.text.strip() if not result.text.strip().startswith('http') else result.text.strip()
                urls.append(base_url)
        
        if len(urls) < num_results:
            results = soup.find_all('a', class_='result__a')
            for result in results:
                if len(urls) >= num_results:
                    break
                href = result.get('href')
                if href and 'duckduckgo.com' not in href:
                    urls.append(href)
        
        return urls
    
    def search_bing(self, query, num_results=10):
        """
        Alternative method to search using Bing.

        Parameters:
        - query: str, the search query
        - num_results: int, number of results to return

        Returns:
        - list of search result URLs
        """
        try:
            enhanced_query = f'"{query}" banned drugs in "India"'
            encoded_query = quote_plus(enhanced_query)
            search_url = f"https://www.bing.com/search?q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.bing.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(search_url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            urls = []
            results = soup.find_all('a', {'class': 'b_algoheader'}) or soup.find_all('a')
            
            for result in results:
                if len(urls) >= num_results:
                    break
                href = result.get('href')
                if href and href.startswith(('http://', 'https://')) and 'bing.com' not in href and 'microsoft.com' not in href:
                    if href not in urls:
                        urls.append(href)
            
            return urls
        except Exception as e:
            # print(f"Error in Bing search: {str(e)}")
            return []
    
    def search_for_sources(self, query, num_results=10):
        """
        Try multiple search engines to get the best results.

        Parameters:
        - query: str, the search query
        - num_results: int, number of results to return

        Returns:
        - list of search result URLs
        """
        urls = self.search_bing(query, num_results)
        
        if len(urls) < num_results // 2:
            enhanced_query = f"{query} banned drugs in India"
            backup_urls = [
                f"https://cdsco.gov.in/opencms/opencms/en/search/?query={enhanced_query}",
                f"https://www.nhp.gov.in/search/site/{enhanced_query}",
                "https://cdsco.gov.in/opencms/opencms/en/Drugs/Drugs/",
                "https://www.medindia.net/doctors/drug_information/home.asp",
                "https://www.mohfw.gov.in/"
            ]
            for url in backup_urls:
                if url not in urls:
                    urls.append(url)
        
        return urls[:num_results]

    @staticmethod
    def fetch_webpage_content(url, user_agents):
        """
        Fetch and parse the content of a webpage.
        
        Parameters:
        - url: str, the URL to fetch
        - user_agents: list, user agents for rotation
        
        Returns:
        - str, the extracted text content
        """
        try:
            headers = {'User-Agent': random.choice(user_agents)}
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'  # Set encoding to handle decoding issues
            soup = BeautifulSoup(response.content, 'html.parser')
            for element in soup(["script", "style", "header", "footer", "nav", "aside"]):
                element.extract()
            main_content = soup.find(['main', 'article', 'div', 'body'])
            text_content = main_content.get_text(separator=' ', strip=True) if main_content else soup.get_text(separator=' ', strip=True)
            lines = [line.strip() for line in text_content.splitlines() if line.strip()]
            return ' '.join(lines)
        except SSLError as e:
            # print(f"SSL error for {url}: {e}")
            return ""  # Return empty string on SSL error
        except Exception as e:
            # print(f"Error fetching content from {url}: {e}")
            return ""

    def analyze_sources(self,bedrock, drug_info, source_contents,additonal_info):
        """
        Analyze the sources to determine if the drug is banned in India.

        Parameters:
        - drug_info: str, name and/or description of the drug
        - source_contents: list of str, text content from each source

        Returns:
        - str, classification results
        """
        formatted_sources = "\n\n---SOURCE---\n\n".join(
            [f"Source {i+1}:\n{content[:3000]}" for i, content in enumerate(source_contents) if content]
        )
        
        prompt = f"""You are a pharmaceutical regulatory expert specialized in Indian drug regulations

    TASK:
        Analyze the provided sources and determine if the drug described below is banned in India.

        DRUG INFORMATION:
        {drug_info}

        ADDITIONAL INFORMATION
        {additonal_info}

        SOURCE CONTENTS:
        {formatted_sources}
      
    DEFINITIONS:
    - BANNED: The drug is completely illegal for all uses (medical, commercial, or otherwise) and cannot be legally manufactured, sold, prescribed, or possessed in India.
    - CONTROLLED DRUG (Not Banned): The drug is regulated, meaning it has restrictions on its usage/dosage but is not entirely prohibited.
    - PRESCRIPTION-BASED DRUG: The drug is legal but only available with a valid prescription.
    - OPEN FOR SALE (Not Banned): The drug is legally available for purchase without restrictions.
    
    ANALYSIS INSTRUCTIONS:
    1. Carefully review all provided source contents.
    2. Look for explicit mentions of the drug being banned, prohibited, or withdrawn in India.
    3. Consider alternative names or formulations of the drug.
    4. Note the recency and reliability of the information.
    5. Identify if the drug appears on any official banned substance lists in India.
    6. If a drug is classified as illegal under acts like the NDPS Act or has strict penalties for possession, it must be classified as "BANNED."
    7. If a drug is allowed for specific medical purposes under regulation, classify it as "CONTROLLED DRUG (Not Banned)."
    8. Do not assume a drug is banned unless there is explicit evidence.
    
    CLASSIFICATION DECISION:
    Based on the evidence, provide:
    1. Classification: "BANNED" or "CONTROLLED DRUG (Not Banned)" or "PRESCRIPTION-BASED DRUG (Not Banned)" or "OPEN FOR SALE (Not Banned)"
    2. Confidence level: LOW, MEDIUM, or HIGH
    3. Justification: Key evidence supporting your classification (cite specific sources)
    4. Alternative status: If not banned, specify if it's restricted, prescription-only, or over-the-counter
    5. Relevant regulations: Mention any specific Indian regulatory acts or notifications.
    
    INSTRUCTIONS:
    1. Strictly use the specified classification categories only.
    2. If a drug is declared completely illegal (e.g., per NDPS Act), classify it as "BANNED."
    3. Only give classification as '"BANNED" or "CONTROLLED DRUG (Not Banned)" or "PRESCRIPTION-BASED DRUG" or "OPEN FOR SALE (Not Banned)"' not include classification analysis in the result.

    OUTPUT STRUCTURE:
    <output>
    <classification> Banned or Not Banned </classification>
    <detailed_classification> "BANNED" or "CONTROLLED DRUG (Not Banned)" or "PRESCRIPTION-BASED DRUG (Not Banned)" or "OPEN FOR SALE (Not Banned)"</detailed_classification>
    <confidence_level> LOW, MEDIUM, or HIGH </confidence_level>
    <justification> Key evidence supporting your classification (cite specific sources) </justification>
    <alternative_status> If not banned, specify if it's restricted, prescription-only, or over-the-counter </alternative_status>
    <relevant_regulations> Mention any specific Indian regulatory acts or notifications. </relevant_regulations>
        """
        
        response = bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']

    def classify_drug(self, bedrock,drug_name_or_description, drug_info):
        # print(f"Starting classification for: {drug_name_or_description}")
        
        # Gather URLs from search and reliable sources
        urls = self.search_for_sources(drug_name_or_description)
        for reliable_source in self.reliable_sources:
            if reliable_source not in urls:
                urls.append(reliable_source)
        
        # print(f"Found {len(urls)} sources to analyze")
        
        # Prepare arguments for multiprocessing
        args = [(url, self.user_agents) for url in urls]
        
        # Fetch content using multiprocessing
        with Pool(processes=cpu_count()) as pool:
            results = pool.starmap(DrugBanClassifier.fetch_webpage_content, args)
        
        # Filter successful fetches (content length > 500)
        source_contents = [content for content in results if content and len(content) > 500]
        successful_urls = [url for url, content in zip(urls, results) if content and len(content) > 500]
        
        # Add fallback info if insufficient sources
        if len(source_contents) < 3:
            fallback_info = """
            List of Some Banned Drugs in India:
            
            1. Fixed Dose Combinations (FDCs):
            - Nimesulide with Paracetamol
            - Aceclofenac with Paracetamol and Rabeprazole
            - Metformin with Pioglitazone
            
            2. Individual drugs:
            - Phenylpropanolamine: Banned in 2011 due to stroke risk
            - Sibutramine: Banned in 2010 due to cardiovascular concerns
            - Cisapride: Banned due to cardiac arrhythmia risk
            - Valdecoxib: Banned due to cardiovascular complications
            - Rofecoxib: Banned due to increased heart attack risk
            
            3. Other notable bans:
            - Analgin (Metamizole): Banned due to risk of agranulocytosis
            - Some formulations of Diclofenac: Restricted due to vulture population decline
            - Oxytocin: Restricted for human use only through public sector to prevent misuse
            - Chloramphenicol for veterinary use: Banned due to potential human health risks
            
            Information provided by Central Drugs Standard Control Organization (CDSCO), India.
            """
            source_contents.append(fallback_info)  # Append fallback info to source_contents
            print("Added fallback information due to insufficient sources")
        
        # Analyze the sources
        result = self.analyze_sources(bedrock,drug_name_or_description, source_contents,drug_info)
        
        # Return the corrected dictionary
        return {
            "drug_info": drug_name_or_description,
            "classification_result": result,
            "sources_analyzed": successful_urls,  # List of successfully fetched URLs
            "successful_sources": len(source_contents)
        }


import re
import xml.etree.ElementTree as ET

def extract_xml(output):
    """Extract the XML portion from the input string."""
    match = re.search(r'<output>.*?</output>', output, re.DOTALL)
    if match:
        return match.group(0)
    return None

def parse_classification_response(output):
    """Parse an XML string and return its contents as a dictionary."""
    # Remove leading/trailing whitespace
    output = output.strip()
    
    # Extract the XML portion
    xml_output = extract_xml(output)
    if not xml_output:
        print("Error: No valid XML found in the input.")
        return None
    
    try:
        # Parse the XML
        root = ET.fromstring(xml_output)
        
        # Verify the root tag is 'output'
        if root.tag != 'output':
            raise ValueError(f"Expected root tag 'output', got '{root.tag}'")
        
        # Extract specific tags
        tags = ['classification', 'detailed_classification', 'confidence_level', 
                'justification', 'alternative_status', 'relevant_regulations']
        result = {
            tag: (root.find(tag).text.strip() if root.find(tag) is not None else None)
            for tag in tags
        }
        return result
    
    except ET.ParseError as e:
        print(f"Error: Unable to parse XML. Details: {e}")
        return None
    except ValueError as e:
        print(f"Error: {e}")
        return None