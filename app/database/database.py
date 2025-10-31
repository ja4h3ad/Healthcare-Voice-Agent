from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
import os
import logging
from datetime import timedelta, datetime
import pytz
# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#  Load the environment variables from .env file
load_dotenv()

mongo_url = os.environ.get('MONGO_URL')
mongo_name = os.environ.get('MONGO_DB_NAME')
dev_mongo_url = os.environ.get('DEV_MONGO_URL')
dev_mongo_name = os.environ.get('DEV_MONGO_DB_NAME')


class Database:
    '''
    1. class called Database that takes in the necessary connection parameters in the constructor method (init).
    2. two methods: create_database() and create_table().
    3. The create_database() method takes a name parameter and creates a new database with the specified name.
    '''
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self, uri=dev_mongo_url, db_name=dev_mongo_name):
        # production
        # self.client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
        # self.db = self.client[os.getenv('MONGO_DB_NAME')]
        # dev connections
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        print("Database object assigned:", self.db)
    async def disconnect(self):
        # Properly close the Motor client
        self.client.close()
        print("Disconnected from MongoDB")

    async def insert_or_update_patient(self, patient_data):
        patients = self.db.patients
        # Check if the patient already exists based on a unique field like mobileNumber
        existing_patient = await patients.find_one({"mobileNumber": patient_data["mobileNumber"]})

        if not existing_patient:
            # No existing patient, perform an insert
            result = await patients.insert_one(patient_data)
            # MongoDB automatically assigns an ObjectId which is accessed by result.inserted_id
            return str(result.inserted_id)  # Return the ObjectId as a string

        # If the patient already exists, perform an update
        await patients.update_one(
            {"mobileNumber": patient_data["mobileNumber"]},
            {"$set": patient_data}
        )
        # Return the ObjectId of the existing patient as a string
        return str(existing_patient['_id'])

    async def insert_doctor(self, doctor_data):
        doctors = self.db.physicians
        # Check if a doctor exists to decide whether to generate a new ID
        existing_doctor = await doctors.find_one({"firstName": doctor_data["firstName"], "lastName": doctor_data["lastName"]})
        if not existing_doctor:
            # Assign a new stringified ObjectId if no existing doctor
            doctor_data['_id'] = str(ObjectId())
        else:
            # Use existing '_id' for updates to maintain ID consistency
            doctor_data['_id'] = str(existing_doctor['_id'])

        result = await doctors.update_one(
            {"firstName": doctor_data["firstName"], "lastName": doctor_data["lastName"]},
            {"$set": doctor_data},
            upsert=True
        )
        return str(doctor_data['_id'])  # Ensure the doctorID is always a string

    async def insert_aesthetician(self, doctor_data):
        aestheticians = self.db.aestheticians
        # Similar logic as for doctors
        existing_aesthetician = await aestheticians.find_one({"firstName": doctor_data["firstName"], "lastName": doctor_data["lastName"]})
        if not existing_aesthetician:
            doctor_data['_id'] = str(ObjectId())
        else:
            doctor_data['_id'] = str(existing_aesthetician['_id'])

        result = await aestheticians.update_one(
            {"firstName": doctor_data["firstName"], "lastName": doctor_data["lastName"]},
            {"$set": doctor_data},
            upsert=True
        )
        return str(doctor_data['_id'])

    async def insert_appointment(self, appointment_dict):
        if '_id' not in appointment_dict:
            appointment_dict['_id'] = ObjectId()

        # Ensure appointmentDateTime is a datetime object
        if isinstance(appointment_dict['appointmentDateTime'], str):
            appointment_dict['appointmentDateTime'] = datetime.strptime(
                appointment_dict['appointmentDateTime'],
                "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=pytz.UTC)

        # Set createdAt and updatedAt
        current_time = datetime.now(pytz.UTC)
        appointment_dict['createdAt'] = current_time
        appointment_dict['updatedAt'] = current_time

        # Calculate endDateTime
        duration = appointment_dict.get('duration', 60)  # default to 60 minutes if not specified
        appointment_dict['endDateTime'] = appointment_dict['appointmentDateTime'] + timedelta(minutes=duration)

        appointment_dict['staffType'] = appointment_dict['appointmentRoute'].lower()

        result = await self.db.appointments.update_one(
            {'_id': appointment_dict['_id']},
            {'$set': appointment_dict},
            upsert=True
        )
        return str(appointment_dict['_id'])

    async def get_patient_info(self, account_number=None, mobile_number=None):
        '''
        Retrieve patient info and appointments based on account number or mobile number.
        '''
        print("Patient query being performed")
        try:
            query = {}
            if account_number:
                query['accountNumber'] = account_number
                print(f"Account number {account_number} has been passed")
            elif mobile_number:
                query['mobileNumber'] = mobile_number
                print(f"Mobile number {mobile_number} has been passed")

            if not query:
                raise ValueError("Either account_number or mobile_number must be provided")

            patient_info = await self.db.patients.find_one(query)

            if patient_info:
                # Fetch appointments using the patient's ID
                appointments = await self.db.appointments.find(
                    {'patientID': str(patient_info['_id'])}
                ).sort('appointmentDateTime', 1).to_list(length=None)
                print(f'Patient appointments: {appointments}')

                return patient_info, appointments
            else:
                print("Patient not found")
                return None, None

        except Exception as e:
            print(f"Error while fetching data: {e}")
            return None, None

    # Add to app/database/database.py

    async def get_patient_by_id(self, patient_id):
        """
        Get patient by MongoDB _id

        Args:
            patient_id: Patient's _id (string or ObjectId)

        Returns:
            Patient document or None
        """
        try:
            patient = await self.db.patients.find_one({"_id": ObjectId(patient_id)})
            return patient
        except Exception as e:
            logger.error(f"Failed to fetch patient by ID: {str(e)}")
            return None


    async def find_doctor_from_physicians(self, doctor_id=None):
        if not doctor_id:
            return None
        query = {'$or': [{'_id': doctor_id}, {'_id': ObjectId(doctor_id)}]}
        doctor = await self.db.physicians.find_one(query)
        if doctor:
            doctor['_id'] = str(doctor['_id'])  # Ensure _id is always a string
        return doctor

    async def find_doctor_from_aestheticians(self, doctor_id=None):
        if not doctor_id:
            return None
        query = {'$or': [{'_id': doctor_id}, {'_id': ObjectId(doctor_id)}]}
        aesthetician = await self.db.aestheticians.find_one(query)
        if aesthetician:
            aesthetician['_id'] = str(aesthetician['_id'])  # Ensure _id is always a string
        return aesthetician

    async def get_provider_info(self, doctor_id):
        # Try to find the provider in the physicians collection
        provider = await self.find_doctor_from_physicians(doctor_id)

        if not provider:
            # If not found in physicians, try the aestheticians collection
            provider = await self.find_doctor_from_aestheticians(doctor_id)

        if provider:
            return {
                "_id": provider['_id'],  # Add this line
                "firstName": provider['firstName'],
                "lastName": provider['lastName'],
                "providerType": "Physician" if await self.find_doctor_from_physicians(doctor_id) else "Aesthetician"
            }
        else:
            print(f"Provider not found for ID: {doctor_id}")
            return {
                "_id": doctor_id,  # Add this line
                "firstName": "Unknown",
                "lastName": "Provider",
                "providerType": "Unknown"
            }
    async def check_staff_availability(self, staff_id, appointment_time, duration, staff_type):
        logger.info(f"Checking availability for {staff_type} with ID {staff_id}")
        logger.info(f"Requested appointment: Start: {appointment_time}, Duration: {duration} minutes")

        end_time = appointment_time + timedelta(minutes=duration)
        logger.info(f"Appointment end time: {end_time}")

        query = {
            'doctorID': staff_id,
            'staffType': staff_type,
            '$or': [
                {'appointmentDateTime': {'$lt': end_time, '$gte': appointment_time}},
                {'endDateTime': {'$gt': appointment_time, '$lte': end_time}},
                {'appointmentDateTime': {'$lte': appointment_time}, 'endDateTime': {'$gte': end_time}}
            ]
        }

        logger.info(f"MongoDB query: {query}")

        existing_appointments = await self.db.appointments.find(query).to_list(length=None)

        logger.info(f"Number of conflicting appointments found: {len(existing_appointments)}")
        for appointment in existing_appointments:
            logger.info(
                f"Conflicting appointment: Start: {appointment['appointmentDateTime']}, End: {appointment['endDateTime']}")

        return len(existing_appointments) == 0

    async def find_available_provider(self, appointment_route, appointment_datetime, duration):
        logger.info(f"Finding available {appointment_route} for {appointment_datetime}, duration: {duration}")
        if appointment_route.lower() == 'physician':
            collection = self.db.physicians
        elif appointment_route.lower() == 'aesthetician':
            collection = self.db.aestheticians
        else:
            raise ValueError("Invalid appointment route")

        # Find all providers of the specified type
        providers = await collection.find().to_list(length=None)
        logger.info(f"Found {len(providers)} providers of type {appointment_route}")

        for provider in providers:
            logger.info(f"Checking availability for provider: {provider['_id']}")
            is_available = await self.check_staff_availability(
                provider['_id'],
                appointment_datetime,
                duration,
                appointment_route.lower()
            )
            if is_available:
                logger.info(f"Provider {provider['_id']} is available")
                return provider
            else:
                logger.info(f"Provider {provider['_id']} is not available")

        logger.info("No available provider found")
        return None  # No available provider found

    async def get_appointment_by_id(self, appointment_id):
        '''
        queries mongo to find a specific appointment
        :param appointment_id:
        :return: appointmemnt dict
        '''
        try:
            document = await self.db.appointments.find_one({"_id":  ObjectId (appointment_id)})# convert the string ID to the mongo ObjectId for querying
            if document:
                return document
            else:
                return None
        except Exception as e:
            logger.error(f"failed to fetch appointment by ID:  {str(e)}")
            return None

    async def update_appointment(self, appointment_id: str, update_data: dict):
        update_data['updatedAt'] = datetime.now(pytz.UTC)

        if 'appointmentDateTime' in update_data and 'duration' in update_data:
            update_data['endDateTime'] = update_data['appointmentDateTime'] + timedelta(minutes=update_data['duration'])
        elif 'appointmentDateTime' in update_data:
            # Fetch current duration if only datetime is being updated
            current_appointment = await self.get_appointment_by_id(appointment_id)
            if current_appointment:
                update_data['endDateTime'] = update_data['appointmentDateTime'] + timedelta(
                    minutes=current_appointment['duration'])

        result = await self.db.appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0



