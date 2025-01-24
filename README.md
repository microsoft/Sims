# Sims

`Sims` is an interactive web tool that helps users find similar geographical regions or cluster areas based on environmental characteristics. Using Google Earth Engine as backend, it allows you to select a reference area and find other locations that share similar features like rainfall patterns, soil composition, vegetation indices, and land cover types. This makes it particularly valuable for agricultural planning, environmental research, and land-use analysis.

## GCP Setup

Before running the application, you'll need to set up Google Cloud Platform credentials. Follow these steps:

1. Install the Google Cloud SDK (gcloud CLI):

   **Windows:**
   - Download the [Google Cloud SDK installer](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe)
   - Run the installer and follow the prompts
   - Restart your terminal after installation

   **macOS:**
   ```bash
   # Using Homebrew
   brew install google-cloud-sdk
   ```

   **Linux:**
   ```bash
   # Add Google Cloud SDK distribution URI as a package source
   echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

   # Import the Google Cloud public key
   curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

   # Update and install the SDK
   sudo apt-get update && sudo apt-get install google-cloud-sdk
   ```

2. Initialize gcloud and authenticate:
   ```bash
   # Initialize gcloud
   gcloud init

   # Log in to your Google Account
   gcloud auth login

   # Set your project ID
   gcloud config set project YOUR_PROJECT_ID
   ```

3. Create a service account and download credentials:
   ```bash
   # Create a service account
   gcloud iam service-accounts create sims-service-account --display-name="Sims Service Account"

   # Generate and download the key file
   gcloud iam service-accounts keys create sims-key.json --iam-account=sims-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. Set the environment variable to point to your credentials:
   ```bash
   # For Linux/macOS
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/sims-key.json"

   # For Windows (PowerShell)
   $env:GOOGLE_APPLICATION_CREDENTIALS="path\to\sims-key.json"
   ```

5. Grant necessary permissions:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:sims-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/storage.objectViewer"
   ```

## Local Development

Install [`mamba`](https://github.com/conda-forge/miniforge).

Setup a new environment, install the required dependencies, and install `Sims` as follows:

```bash
mamba create -n sims python=3.12.3
conda activate sims
mamba install conda-forge::gdal
pip install -r requirements.txt
pip install -e .
```

You can run the app locally:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/sims-key.json"
cd scripts/
solara run app.py
```

## Deploy

You can deploy the app using Docker as follows:

### Build the Docker Image

1. Clone this repository or move the repository to your deployment machine.
2. Copy your GCP credentials file into the project directory:
   ```bash
   cp path/to/sims-key.json ./credentials.json
   ```
   
   > ⚠️ Make sure to add `credentials.json` to your `.gitignore` file to avoid accidentally committing sensitive credentials.

3. Build the Docker image by running the following command in the project directory:
   ```bash
   docker build -t sims-app .
   ```

   This will create a Docker image named `sims-app` based on the `Dockerfile` in the repository.

### Run the App

You have two options for providing GCP credentials to the container:

#### Option 1: Mount credentials file (Recommended for development)
```bash
docker run -it \
  -p 8080:8080 \
  -v $(pwd)/credentials.json:/app/credentials.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  sims-app
```

#### Option 2: Pass credentials as an environment variable (Recommended for production)
```bash
# Export the content of your credentials file as a base64-encoded string
export GOOGLE_CREDENTIALS=$(base64 -w 0 credentials.json)

# Run the container with the encoded credentials
docker run -it \
  -p 8080:8080 \
  -e GOOGLE_CREDENTIALS="$GOOGLE_CREDENTIALS" \
  sims-app
```

> 📝 For Windows PowerShell, use this command to encode credentials:
> ```powershell
> $env:GOOGLE_CREDENTIALS = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Content -Raw credentials.json)))
> ```

### Access the App

Once the app is running, you can access it from your browser by visiting:

```
http://localhost:8080
```

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

## License

This project is licensed under the [MIT License](LICENSE).