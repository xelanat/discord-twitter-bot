current_date=$(date +"%Y%m%d%H%M%S")
deployment_filename="deployment-package-${current_date}.zip"
pip install -r requirements.txt --target ./package
zip -r $deployment_filename package
zip -g $deployment_filename lambda_function.py