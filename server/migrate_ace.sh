# You most likely want to change this. Refer to https://github.com/golang-migrate/migrate.
MIGRATE_COMMAND="up"

IMAGE_REPO=024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/third_party/migrate
IMAGE_TAG=latest
NAMESPACE=ten-0c8a9114-fddc-4251-b546-13b99bd7dd9e

# Get the postgres connection details
POSTGRES_PASSWORD=$(kubectl get secret agents-postgres -n $NAMESPACE -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 --decode)
POSTGRES_DB=$(kubectl get configmap agents-postgres -n $NAMESPACE -o jsonpath='{.data.POSTGRES_DB}')
POSTGRES_HOST=$(kubectl get configmap agents-postgres -n $NAMESPACE -o jsonpath='{.data.POSTGRES_HOST}')
POSTGRES_PORT=$(kubectl get configmap agents-postgres -n $NAMESPACE -o jsonpath='{.data.POSTGRES_PORT}')
POSTGRES_USER=$(kubectl get configmap agents-postgres -n $NAMESPACE -o jsonpath='{.data.POSTGRES_USER}')

# Create the entrypoint script
cat <<EOF > entrypoint.migrate.sh
#!/bin/sh
migrate -path /migrations -database postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?sslmode=disable $MIGRATE_COMMAND
EOF
chmod +x entrypoint.migrate.sh

# Build the migrate image
cat <<EOF > Dockerfile.migrate
FROM migrate/migrate
COPY sema4ai_agent_server/migrations/postgres /migrations/
COPY entrypoint.migrate.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
EOF
docker build -t $IMAGE_REPO:$IMAGE_TAG -f Dockerfile.migrate .

# Clean up the files
rm Dockerfile.migrate
rm entrypoint.migrate.sh

# Push the image to ECR
export AWS_PROFILE=context-sso
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $IMAGE_REPO
docker push $IMAGE_REPO:$IMAGE_TAG

# Create the migrate job in k8s
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: postgres-setup-$(date +%s)
  namespace: $NAMESPACE
  annotations:
    migrate-command: $MIGRATE_COMMAND
spec:
  template:
    spec:
      containers:
      - name: postgres-setup
        image: $IMAGE_REPO:$IMAGE_TAG
      restartPolicy: Never
  backoffLimit: 4
EOF