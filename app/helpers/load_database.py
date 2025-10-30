import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
from database import Database  # Ensure this is properly imported
from models import Patient, DoctorBase, AestheticianBase
import asyncio

# Initialize your database
db = Database()
asyncio.run(db.connect())  # Make sure to connect asynchronously

async def load_csv_data(file_path, model, collection):
    df = pd.read_csv(file_path, dtype={'mobileNumber': str, 'accountNumber': str, 'postCode': str})  # Ensure string type
    # Process each row in the dataframe
    for _, row in df.iterrows():
        data = row.to_dict()
        # Convert fields to datetime or perform other transformations as necessary
        if 'dob' in data:
            data['dob'] = pd.to_datetime(data['dob']).to_pydatetime()
        if 'createdAt' in data or 'updatedAt' in data:
            data['createdAt'] = data['updatedAt'] = pd.Timestamp.now().to_pydatetime()
        # Create a Pydantic model instance
        model_instance = model(**data)
        # Insert into database
        if collection == 'patients':
            result = await db.insert_or_update_patient(model_instance.dict())
        elif collection == 'physicians':
            result = await db.insert_doctor(model_instance.dict())
        elif collection == 'aestheticians':
            result = await db.insert_aesthetician(model_instance.dict())
        print(f"Inserted {collection[:-1]} with ID: {result}")


# Load data from CSV files
async def load_data():
    await load_csv_data('aestheticians.csv', AestheticianBase, 'aestheticians')
    await load_csv_data('physicians.csv', DoctorBase, 'physicians')
    await load_csv_data('patients.csv', Patient, 'patients')

# Run the loading function
if __name__ == '__main__':
    asyncio.run(load_data())
