import streamlit as st
import requests
import base64
import json
import boto3
import mimetypes
from io import BytesIO
from PIL import Image
from rapidfuzz import fuzz, process


# Load AWS credentials from access_key.json
with open('access_key2.json', 'r') as f:
    credentials = json.load(f)
    AWS_ACCESS_KEY_ID = credentials['Access_key_ID']
    AWS_SECRET_ACCESS_KEY = credentials['Secret_access_key']

# Initialize Bedrock client with credentials
bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Load the pharma_images_dict.json
with open('pharma_images_dict.json', 'r') as f:
    pharma_images_dict = json.load(f)

def encode_image_to_base64(image_bytes, file_extension):
    media_type = f"image/{file_extension}" if file_extension else "image/jpeg"
    return base64.b64encode(image_bytes).decode('utf-8'), media_type

def fetch_image_from_url(image_url):
    try:
        response = requests.get(image_url, timeout=5)
        response.raise_for_status()
        image_bytes = response.content
        content_type = response.headers.get('Content-Type', '')
        file_extension = mimetypes.guess_extension(content_type).lstrip('.') if content_type else 'jpg'
        return image_bytes, file_extension
    except requests.exceptions.RequestException as e:
        return None, str(e)

def query_bedrock_llm_images(image_base64, prompt):
    # Prepare the input for the multimodal model
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {
                "role": "user",
                "content": [
                    image_base64,
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 1700,
        "temperature": 0.1
    })
    accept = 'application/json'
    contentType = 'application/json'
    # Invoke the model
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',  # Use Claude 3 Sonnet
        body=body, accept=accept, contentType=contentType
    )
    return response['body'].read().decode('utf-8')


def query_bedrock_llm(prompt):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_tokens": 1700,
        "temperature": 0.1
    })
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=body,
            accept='application/json',
            contentType='application/json'
        )
        return response['body'].read().decode('utf-8')
    except Exception as e:
        return json.dumps({"error": str(e)})

def process_llm_response(result):
    try:
        result_json = json.loads(result)
        content = result_json.get('content', [])
        if content and isinstance(content, list) and len(content) > 0:
            return json.loads(content[0].get('text', '{}'))
    except Exception as e:
        return {"error": f"Failed to parse response: {str(e)}"}
    return {"error": "No valid content found"}

def main():
    st.title("🩺 Pharma Product Analyzer")
    option = st.radio("Choose input type:", ["Upload Image", "Image URL"])
    json_input = st.text_area("Enter JSON data (pc_item_id, pname, description, isq):")
    json_data = {}
    if json_input:
        try:
            json_data = json.loads(json_input)
        except json.JSONDecodeError:
            st.error("Invalid JSON input. Please provide valid JSON data.")
    image_bytes = None
    file_extension = None
    image_urls = []

    if option == "Upload Image":
        uploaded_files = st.file_uploader("Upload pharmaceutical product images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_extension = uploaded_file.type.split('/')[-1]
                image_bytes = uploaded_file.read()
                image_base64, media_type = encode_image_to_base64(image_bytes, file_extension)
                image_urls.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}})

    elif option == "Image URL":
        image_url_input = st.text_area("Enter multiple image URLs (comma-separated)")
        if st.button("Fetch Images"):
            urls = [url.strip() for url in image_url_input.split(',') if url.strip()]
            for url in urls:
                image_bytes, error_or_ext = fetch_image_from_url(url)
                if image_bytes:
                    file_extension = error_or_ext
                    image_base64, media_type = encode_image_to_base64(image_bytes, file_extension)
                    image_urls.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}})
                else:
                    st.error(f"Failed to fetch image: {error_or_ext}")
            st.info("Images fetched successfully!")

    if not image_urls and json_data.get('pc_item_id'):
        product_id = json_data['pc_item_id']
        if product_id in pharma_images_dict:
            urls = pharma_images_dict[product_id]
            for url in urls:
                image_bytes, error_or_ext = fetch_image_from_url(url)
                if image_bytes:
                    file_extension = error_or_ext
                    image_base64, media_type = encode_image_to_base64(image_bytes, file_extension)
                    image_urls.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}})
            st.info("Images fetched successfully!")

    if json_data or image_urls:
        # Step 2: Prepare the prompt for the LLM
        with open('banned_drugs.json', 'r') as f:
            bannedDrugs = json.load(f)

        # Fuzzy match function
        def find_best_match(pname, banned_drugs, threshold=80):
            best_match = None
            best_score = 0

            for drug in banned_drugs:
                drug_name = drug["drug_name"]
                score = fuzz.ratio(pname.lower(), drug_name.lower())  # Compute similarity

                if score > best_score and score >= threshold:
                    best_match = drug
                    best_score = score

            return best_match, best_score
      
        prompt = """
        You are an expert in pharmaceutical regulations and drug classification. Given an image of a pharmaceutical product label, perform the following tasks:

        1. **Extract and structure the following pharmaceutical information:**
           - **Product Name**
           - **Salt Composition**
           - **Dosage Strength**
           - **Formulation Type** (e.g., Tablet, Capsule, Syrup)
           - **Quantity** (e.g., 10 Tablets, 100 Capsules)
           - **Prescription Status** (Rx Only, OTC, Controlled Drug)
           - **Manufacturer**    
        2. **Return the structured JSON output with these details:**
        ```json
        {
            "Product Name": "<Extracted Product Name>",
            "Salt Composition": "<Extracted Salt Composition>",
            "Dosage Strength": "<Extracted Dosage Strength>",
            "Formulation Type": "<Extracted Formulation>",
            "Quantity": "<Extracted Quantity>",
            "Prescription Status": "<Rx Only / OTC / Controlled Drug / NA>",
            "Manufacturer": "<Extracted Manufacturer>"
        }
        ```
        """ 
        if image_urls:
            st.info("Analyzing each image for information...")

        prd_image_details= []
        for image_url in image_urls:
            result = query_bedrock_llm_images(image_url, prompt)
            prd_image_details.append(result)

        if image_urls:
            st.info("Image analysis completed!")
            
        combined_prompt = {
            "prd_name": json_data.get('pname', ''),
            "prd_description": json_data.get('description', ''),
            "prd_isq": json_data.get('isq', ''),
            "prd_img_details": prd_image_details,
            "banned_drug_list": bannedDrugs["banned_drugs"]
        }

        
        if st.button("Analyze Product"):
            st.info("Processing product details with AWS Bedrock LLM...")
              # Run matching
            best_match, score = find_best_match(json_data["pname"], bannedDrugs["banned_drugs"])

            # Print result
            if best_match and score >= 60:
                response = {
                                "classification": "Banned",
                                "detailed_classification": "Banned, not for sale",
                                "confidence_level": f"Similarity Score: {score}%",
                                "justification": "Found in banned_drug_list",
                                "matched_drug": best_match["drug_name"],
                                "notification_no": best_match["notification_no"],
                                "date": best_match["date"]
                            }
                st.json(response)
            else:
                st.info(f"No exact match found in the banned drug list. Similarity is {score}%. Proceeding with further analysis.")
            # Call the LLM with the combined prompt
                import prediction as pred
                classifier = pred.DrugBanClassifier()
                st.info("\nSearching for information about the drug's banned status in India...")
                result = classifier.classify_drug(bedrock,json_data.get('pname', ''),combined_prompt)
                st.json(pred.parse_classification_response(result['classification_result']))

            if st.button("Restart Analysis"):
                st.experimental_rerun()

    else:
        st.warning("Please provide product details (JSON) and/or upload an image or provide a valid URL.")

if __name__ == "__main__":
    main()