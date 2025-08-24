# FastAPI Notes Application

This project implements a simple Notes API using FastAPI, backed by AWS DynamoDB for data storage. The application allows users to create, list, retrieve, update, and delete notes. It is designed to be deployed as an AWS Lambda function using a Docker.

## Features

- **Create Note**: Add a new note with a title and content. A summary is automatically generated.
- **List Notes**: Retrieve all existing notes.
- **Get Note by ID**: Fetch a specific note using its unique ID.
- **Update Note**: Modify an existing note's title and content.
- **Delete Note**: Remove a note by its ID.
- **DynamoDB Integration**: Uses AWS DynamoDB as the persistent data store. The application automatically creates the DynamoDB table if it doesn't exist.
- **CORS Enabled**: Configured to allow cross-origin requests from any origin.

## Technologies Used

- **FastAPI**: A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
- **Pydantic**: Used for data validation and settings management with Python type annotations.
- **Boto3**: The Amazon Web Services (AWS) SDK for Python, used to interact with DynamoDB.
- **Mangum**: An adapter for running ASGI applications (like FastAPI) on AWS Lambda and Amazon API Gateway.
- **Docker**: Used to containerize the application for deployment to AWS Lambda.

## Project Structure

- `app/app.py`: Contains the main FastAPI application logic, including API endpoints, DynamoDB interactions, and the Lambda handler.
- `Dockerfile`: Defines the Docker image for the application, based on the AWS Lambda Python 3.11 base image.
- `requirements.txt`: Lists the Python dependencies required by the application.
- `.github/workflows/deploy.yml`: Defines the GitHub Actions workflow for CI/CD.

## CI/CD with GitHub Actions

This project uses GitHub Actions for continuous integration and continuous deployment (CI/CD) to AWS Lambda. The workflow is triggered on every push to the `main` branch.

The `deploy.yml` workflow performs the following steps:

1.  **Checkout Code**: Fetches the latest code from the repository.
2.  **Set up Python**: Configures Python 3.11 environment.
3.  **Install Dependencies**: Installs Python packages listed in `requirements.txt`.
4.  **Configure AWS Credentials**: Sets up AWS credentials using GitHub Secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) and the specified `AWS_REGION`.
5.  **Login to Amazon ECR**: Authenticates Docker with Amazon Elastic Container Registry (ECR).
6.  **Build Docker Image**: Builds the Docker image for the FastAPI application. The image is tagged with the ECR repository URI.
7.  **Push Docker Image to ECR**: Pushes the built Docker image to the specified ECR repository (`fastapi-notes-app`).
8.  **Update Lambda Function**: Updates the AWS Lambda function (`fastapi-notes-app`) with the newly pushed Docker image.

### Environment Variables for CI/CD

The following environment variables are used in the GitHub Actions workflow:

-   `AWS_REGION`: The AWS region where resources are deployed (e.g., `ap-south-1`).
-   `ECR_REPO`: The name of the ECR repository (e.g., `fastapi-notes-app`).
-   `LAMBDA_FUNCTION_NAME`: The name of the AWS Lambda function (e.g., `fastapi-notes-app`).

### AWS Credentials

The deployment workflow requires AWS credentials to be configured as GitHub Secrets:

-   `AWS_ACCESS_KEY_ID`
-   `AWS_SECRET_ACCESS_KEY`

These credentials must have the necessary permissions to interact with ECR and Lambda services.
