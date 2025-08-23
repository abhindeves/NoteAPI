# Use the AWS Lambda Python 3.11 base image
FROM public.ecr.aws/lambda/python:3.11


# Install dependencies into the Lambda task root
COPY requirements.txt ./
RUN pip3 install --upgrade pip && \
pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"


# Copy application
COPY app.py ${LAMBDA_TASK_ROOT}/app.py


# Set the Lambda handler (module.handler)
CMD ["app.handler"]