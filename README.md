# Sims

This repository contains the source code for `Sims: An Interactive Tool for Geospatial Feature Discovery`.

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
cd scripts/
solara run app.py
```

## Deploy

You can deploy the app using Docker as follows:

### Build the Docker Image

1. Clone this repository or move the repository to your deployment machine.
2. Build the Docker image by running the following command in the project directory:

```
docker build -t sims-app .
```

This will create a Docker image named `sims-app` based on the `Dockerfile` in the repository.

### Run the App
```
docker run -it -p 8080:8080 sims-app
```

This will start the app inside the container.

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