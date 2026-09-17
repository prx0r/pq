from pathlib import Path

def package_data_root()->Path:
    return Path(__file__).resolve().parent/'data'

def packaged_processors()->Path:
    return package_data_root()/'processors'

def packaged_recovery()->Path:
    return package_data_root()/'recovery'/'recipes.json'

def packaged_modules()->Path:
    return package_data_root()/'modules'
