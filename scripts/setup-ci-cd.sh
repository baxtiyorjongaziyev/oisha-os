#!/bin/bash

# Oisha-OS CI/CD Setup Script
# This script helps configure automatic deployment to Google Cloud Run

set -e

echo "🚀 Oisha-OS CI/CD Setup"
echo "========================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="jonbranding-85662071-ea38e"
SERVICE_NAME="oisha-master-bot"
REGION="europe-west3"
REPO_NAME="oisha-os"

echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first:${NC}"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ Not logged in to gcloud. Run: gcloud auth login${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites met${NC}"
echo ""

# Set project
gcloud config set project $PROJECT_ID

echo -e "${YELLOW}Step 2: Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
#gcloud services enable run.googleapis.com
#gcloud services enable secretmanager.googleapis.com
#gcloud services enable artifactregistry.googleapis.com

echo -e "${GREEN}✅ APIs enabled${NC}"
echo ""

echo -e "${YELLOW}Step 3: Setting up secrets in Secret Manager...${NC}"
echo "The following secrets need to be configured:"
echo "  - BOT_TOKEN"
echo "  - API_ID"
echo "  - API_HASH"
echo "  - GEMINI_API_KEY"
echo "  - OISHA_API_SECRET"
echo "  - AMOCRM_CLIENT_ID"
echo "  - AMOCRM_CLIENT_SECRET"
echo "  - AMOCRM_REDIRECT_URL"
echo "  - GCS_BUCKET"
echo "  - GOOGLE_SERVICE_ACCOUNT_JSON"
echo ""

# Function to create or update secret
create_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if gcloud secrets describe $secret_name &>/dev/null; then
        echo "  Updating existing secret: $secret_name"
        echo "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "  Creating new secret: $secret_name"
        echo "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# Check if user wants to set up secrets now
read -p "Do you want to set up secrets now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Please enter the following values:"
    
    read -p "BOT_TOKEN: " BOT_TOKEN
    create_secret "BOT_TOKEN" "$BOT_TOKEN"
    
    read -p "API_ID: " API_ID
    create_secret "API_ID" "$API_ID"
    
    read -p "API_HASH: " API_HASH
    create_secret "API_HASH" "$API_HASH"
    
    read -p "GEMINI_API_KEY: " GEMINI_API_KEY
    create_secret "GEMINI_API_KEY" "$GEMINI_API_KEY"
    
    read -p "OISHA_API_SECRET: " OISHA_API_SECRET
    create_secret "OISHA_API_SECRET" "$OISHA_API_SECRET"
    
    read -p "AMOCRM_CLIENT_ID: " AMOCRM_CLIENT_ID
    create_secret "AMOCRM_CLIENT_ID" "$AMOCRM_CLIENT_ID"
    
    read -p "AMOCRM_CLIENT_SECRET: " AMOCRM_CLIENT_SECRET
    create_secret "AMOCRM_CLIENT_SECRET" "$AMOCRM_CLIENT_SECRET"
    
    read -p "AMOCRM_REDIRECT_URL: " AMOCRM_REDIRECT_URL
    create_secret "AMOCRM_REDIRECT_URL" "$AMOCRM_REDIRECT_URL"
    
    read -p "GCS_BUCKET: " GCS_BUCKET
    create_secret "GCS_BUCKET" "$GCS_BUCKET"
    
    echo "GOOGLE_SERVICE_ACCOUNT_JSON (paste the entire JSON, press Ctrl+D when done):"
    GOOGLE_SA_JSON=$(cat)
    create_secret "GOOGLE_SERVICE_ACCOUNT_JSON" "$GOOGLE_SA_JSON"
    
    echo -e "${GREEN}✅ Secrets configured${NC}"
else
    echo -e "${YELLOW}⚠️  Skipping secret setup. You can set them up later with:${NC}"
    echo "  echo 'SECRET_VALUE' | gcloud secrets create SECRET_NAME --data-file=-"
fi

echo ""

echo -e "${YELLOW}Step 4: Setting up GitHub Actions...${NC}"
echo "You need to add the following to your GitHub repository secrets:"
echo "  - GCP_SA_KEY: Service account key with Cloud Run and Secret Manager access"
echo "  - OWNER_ID: Your Telegram ID for deployment notifications"
echo ""

# Create service account for GitHub Actions
echo "Creating service account for GitHub Actions..."
SA_NAME="github-actions-oisha"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

if gcloud iam service-accounts describe $SA_EMAIL &>/dev/null; then
    echo -e "${YELLOW}  Service account already exists: $SA_EMAIL${NC}"
else
    gcloud iam service-accounts create $SA_NAME \
        --display-name="GitHub Actions for Oisha-OS"
    echo -e "${GREEN}  ✅ Service account created${NC}"
fi

# Grant necessary permissions
echo "  Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.admin" \
    --condition=None \
    --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudbuild.builds.editor" \
    --condition=None \
    --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/artifactregistry.writer" \
    --condition=None \
    --quiet

echo -e "${GREEN}✅ Permissions granted${NC}"

# Generate and download key
echo ""
echo -e "${YELLOW}Step 5: Generating service account key...${NC}"
KEY_FILE="github-actions-key.json"

gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$SA_EMAIL \
    --key-file-type=json

echo -e "${GREEN}✅ Key generated: $KEY_FILE${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Add this key to GitHub Secrets:${NC}"
echo "  1. Go to: https://github.com/YOUR_USERNAME/$REPO_NAME/settings/secrets/actions"
echo "  2. Click 'New repository secret'"
echo "  3. Name: GCP_SA_KEY"
echo "  4. Value: Copy the contents of $KEY_FILE"
echo "  5. Click 'Add secret'"
echo ""
echo -e "${YELLOW}Also add:${NC}"
echo "  - OWNER_ID: Your Telegram user ID"
echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Push this code to GitHub (main or master branch)"
echo "  2. Automatic deployment will trigger on every push"
echo "  3. Check deployment status in GitHub Actions tab"
echo ""
echo "Commands:"
echo "  git add ."
echo "  git commit -m 'Setup CI/CD for automatic deployment'"
echo "  git push origin main"
