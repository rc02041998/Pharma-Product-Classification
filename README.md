# Pharma Product Classification

This project classifies pharmaceutical products as **Banned** or **Not Banned** based on given product information and/or product images (URLs/Links).

## Solution Workflow

1. **Extract Information from Images**
   - If product images are provided, an LLM extracts relevant details from them.
   - Extracted information is appended to the existing product info.

2. **Web Scraping for Additional Data**
   - The product name is used to search/crawl/scrape the web for supplementary product details.
   - Retrieved information is merged with the provided product info.

3. **Final Classification Using LLM**
   - The combined product details and web scraping results are sent to an LLM.
   - Based on predefined classification criteria, the LLM determines whether the drug is **Banned** or **Not Banned**.

## How to Run

Execute the following command in the terminal:
```sh
streamlit run app.py
```

access the application via:
[Pharma Classification App](https://mmworrier.notebook.us-east-1.sagemaker.aws/proxy/8501/)

## Sample Input

### JSON Input:
```json
{
    "pc_item_id": 277619498,
    "pname": "oral semaglutide tablets for weight loss 3mg 7mg 14mg tablets",
    "description": "rybelsus® semaglutide tablets 3mg 7 mg or 14 mg is a prescription medicine used along with diet and exercise to improve blood sugar glucose in adults with type 2 diabetes it is not known if rybelsus® can be used in people who have had pancreatitis rybelsus® is not for use in people with type 1 diabetes it is not known if rybelsus® is safe and effective for use in children under 18 years of age key takeaways rybelsus semaglutide is an oral medication approved to treat type 2 diabetes it contains the same active ingredient as ozempic and wegovy ozempic is approved for type 2 diabetes and wegovy is approved for chronic weight management rybelsus is currently being studied for weight loss in clinical trials these studies involve higher doses than what’s currently approved and available for diabetes results show that an oral semaglutide rybelsus dose of 50 mg results in similar weight loss as wegovy due to these findings rybelsus’ manufacturer plans to request fda approval in 2023 if approved for weight loss it may be marketed under a different brand name",
    "isq": "box tablets novo nordisk 24 months to treat type 2 diabetes prescription semaglutide prescription made in india"
}
```

### Image URLs:
```text
http://5.imimg.com/data5/SELLER/Default/2024/4/412309997/SH/UY/LV/214400819/aderalll-30mg-tablets.webp,
http://5.imimg.com/data5/SELLER/Default/2024/4/412310001/DI/ID/CX/214400819/aderalll-30mg-tablets.webp
```

## Sample Output

```json
{
    "classification": "Not Banned",
    "detailed_classification": "PRESCRIPTION-BASED DRUG (Not Banned)",
    "confidence_level": "MEDIUM",
    "justification": "None of the sources explicitly mention Adderall or its generic name (amphetamine/dextroamphetamine) as being banned in India. The drug does not appear on any of the banned substance lists provided. However, as a stimulant medication, it is likely to be tightly regulated.",
    "alternative_status": "Prescription-only, likely with additional controls as a psychotropic substance",
    "relevant_regulations": "Likely regulated under the Narcotic Drugs and Psychotropic Substances Act, 1985 and the Drugs and Cosmetics Act, 1940"
}
```

## Improvements & Future Enhancements

1. **Performance Optimization**
   - Implement **multiprocessing** and **multithreading** to reduce processing time.

2. **Database for Keyword Tracking**
   - Maintain a **database/JSON file** to store keyword statuses.
   - Create a separate script to periodically update the database instead of crawling the web on each request, improving efficiency.

---

This project aims to streamline pharmaceutical compliance checks efficiently by leveraging **LLMs, web scraping, and image analysis**.

