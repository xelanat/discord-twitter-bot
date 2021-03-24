pip install -r requirements.txt --target ./package
zip -r my-deployment-package.zip package
zip -g my-deployment-package.zip lambda_function.py