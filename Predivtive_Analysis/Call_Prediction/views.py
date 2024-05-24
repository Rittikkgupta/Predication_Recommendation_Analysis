##########IMPORT##################
import json
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse
from rest_framework.views import APIView
from django.views import View
from sqlalchemy import text , create_engine
from sqlalchemy import create_engine, MetaData
import pyodbc
import re
import pandas as pd
import numpy as np
import calendar
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import pyttsx3
from rest_framework.response import Response
from rest_framework import status
import requests
from django.shortcuts import render, HttpResponse



logger = logging.getLogger(__name__)
def database():
        NAME = 'CognicxContextCentre_AWS'
        HOST = 'DESKTOP-21ATSCV'
        USER = 'sa'
        PASSWORD = 'sa123'
        engine = create_engine(f'mssql+pyodbc://{USER}:{PASSWORD}@{HOST}/{NAME}?driver=ODBC+Driver+17+for+SQL+Server')
        return engine

class Show_Column(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            # Parse request data
            request_data = json.loads(request.body.decode('utf-8'))
            attribute = request_data.get('attribute')
            self.logger.info("Attribute: %s", attribute)

            # Connect to the database
            engine = database()
            conn = engine.connect()

            # Execute SQL query
            query = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'AgentActivityDetails'"
            response_data = pd.read_sql(query, conn)

            # Close the connection
            conn.close()

            # Check if response_data is not empty
            if not response_data.empty:
                # Convert DataFrame to list and return JSON response
                column_list = response_data['COLUMN_NAME'].tolist()
                response = {'responseMessage': 'Success', 'responseCode': 200, 'data': column_list, 'error': ''}
                return JsonResponse(response)
            else:
                response = {'responseMessage': 'Table not found or has no columns', 'responseCode': 404, 'data': [], 'error': ''}
                return JsonResponse(response, status=404)

        except Exception as e:
            # Handle exceptions
            error_message = str(e)
            response = {'responseMessage': 'Error during data fetching', 'responseCode': 400, 'data': [], 'error': error_message}
            self.logger.warning(f"Error during data fetching - {response}")
            return JsonResponse(response, status=400)
    

class Update_Rules(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            # Parse request data
            request_data = json.loads(request.body.decode('utf-8'))
            attribute = request_data.get('attribute')
            formula = request_data.get('formula')
            self.logger.info("Attribute: %s, Formula: %s", attribute, formula)
            print("Attribute: %s, Formula: %s", attribute, formula)

            engine = database()
            conn = engine.connect()

            # Execute the update query
            query = text("EXEC InsertOrUpdatePredictionRule @Attribute=:attribute, @current_formula=:current_formula")
            conn.execute(query, {"attribute": attribute, "current_formula": formula})
            conn.commit()
            conn.close()

            # Prepare response data
            response_data = {
                'responseMessage': 'Updated successfully',
                'responseCode': status.HTTP_200_OK,
                'data': {'attribute': attribute, 'formula': formula},
                'error': ''
            }
            self.logger.info(f"Successful data Fetched {attribute} - {response_data}")
            return JsonResponse(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle exceptions
            error_message = str(e)
            response_data = {
                'responseMessage': 'Error during data update',
                'responseCode': status.HTTP_400_BAD_REQUEST,
                'data': [],
                'error': error_message
            }
            self.logger.warning(f"Error during data update - {response_data}")
            return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)


class FormulaStandardFormula(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            # Parse request data
            request_data = json.loads(request.body.decode('utf-8'))
            attribute = request_data.get('attribute')
            self.logger.info("Attribute: %s", attribute)

            # Connect to the database
            engine = database()  # Replace 'your_database_connection_string' with the actual connection string
            conn = engine.connect()

            # Execute SQL query
            query = text("SELECT current_formula, standard_formula FROM Show_rules WHERE attribute = '{}'".format(attribute))
            result = conn.execute(query)

            # Fetch the result as a DataFrame
            response_data = pd.DataFrame(result.fetchall(), columns=result.keys())

            # Close the connection
            conn.close()

            # Format the 'formula' field
            formatted_data = []
            for index, row in response_data.iterrows():
                formatted_formula = ' '.join(row['current_formula'].split())  # Remove extra whitespace
                formatted_data.append({
                    'attribute': attribute,
                    'current_formula': formatted_formula,
                    'standard_formula': row['standard_formula']
                })

            # Construct the JSON response
            response = {'responseMessage': 'Success', 'responseCode': 200, 'data': formatted_data, 'error': ''}
            return JsonResponse(response)

        except Exception as e:
            # Handle exceptions
            error_message = str(e)
            response = {'responseMessage': 'Error during data fetching', 'responseCode': 400, 'data': [], 'error': error_message}
            self.logger.warning(f"Error during data fetching - {response}")
            return JsonResponse(response, status=400)

        
#  added reason and recommendation for the no. of calls 
class CallsPredictJson(View):
    logger = logging.getLogger(__name__)

    def create_model(self, X_train, y_train):
        try:
            # Initialize and train the Random Forest model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            return model
        except Exception as e:
            self.logger.error(f"An error occurred while training the model: {e}")
            return None

    def preprocess_data(self, data):
        try:
            # Convert 'OriginatedStamp' column to datetime
            data['OriginatedStamp'] = pd.to_datetime(data['OriginatedStamp'])

            # Extract features from 'OriginatedStamp'
            data['year'] = data['OriginatedStamp'].dt.year
            data['month'] = data['OriginatedStamp'].dt.month
            data['day'] = data['OriginatedStamp'].dt.day

            return data
        except Exception as e:
            self.logger.error(f"Error occurred during data preprocessing: {e}")
            return None

    def predict_calls(self, year, month, model):
        try:
            # Create a range of dates for the requested month
            last_day_of_month = datetime(year, month, 1) + timedelta(days=32)
            last_day_of_month = last_day_of_month.replace(day=1) - timedelta(days=1)
            dates = pd.date_range(start=f'{year}-{month}-01', end=last_day_of_month, freq='D')

            # Prepare features for the dates
            future_X = pd.DataFrame({
                'year': dates.year,
                'month': dates.month,
                'day': dates.day
            })

            # Predict calls for the requested month if model exists
            if model:
                predicted_calls = model.predict(future_X)
                response_data = {"predicted_calls": list(predicted_calls)}
            else:
                response_data = {"error": "Model is not trained."}

            return response_data
        except Exception as e:
            self.logger.error(f"Error occurred during prediction: {e}")
            return {"error": "Prediction failed."}

    def train_model_monthly_ensemble(self, start_date, end_date):
        try:
            # Create database engine
            engine = database()

            # Fetch historical data from the database within the given date range
            historical_data_query = f"SELECT OriginatedStamp FROM dbo.CustomerCallDetails"
            historical_data = pd.read_sql(historical_data_query, engine)

            # Preprocess the historical data
            historical_data = self.preprocess_data(historical_data)

            if historical_data is not None:
                # Aggregate data to get the count of calls per day for historical data
                historical_daily_calls = historical_data.groupby(['year', 'month', 'day']).size().reset_index(name='calls')

                # Prepare features and target variable for training
                X = historical_daily_calls[['year', 'month', 'day']]
                y = historical_daily_calls['calls']

                # Split data into train and test sets
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                # Initialize individual models
                model_rf = RandomForestRegressor(n_estimators=100, random_state=42)
                model_gb = GradientBoostingRegressor(n_estimators=100, random_state=42)

                # Create an ensemble model using VotingRegressor
                ensemble_model = VotingRegressor([('rf', model_rf), ('gb', model_gb)])
                
                # Train the ensemble model
                ensemble_model.fit(X_train, y_train)

                # Evaluate the ensemble model
                y_pred = ensemble_model.predict(X_test)
                mae = mean_absolute_error(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)

                print(f"Mean Absolute Error: {mae}")
                print(f"Mean Squared Error: {mse}")
                print(f"Root Mean Squared Error: {rmse}")

                return ensemble_model
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error occurred during monthly ensemble model training: {e}")
            return None

    def fetch_actual_data(self, year, month):
        try:
            # Create database engine
            engine = database()

            # Fetch actual data from the database based on user request
            actual_data_query = f"SELECT COUNT(*) as calls, DAY(OriginatedStamp) as day FROM dbo.CustomerCallDetails WHERE YEAR(OriginatedStamp) = {year} AND MONTH(OriginatedStamp) = {month} GROUP BY YEAR(OriginatedStamp), MONTH(OriginatedStamp), DAY(OriginatedStamp)"
            actual_data = pd.read_sql(actual_data_query, engine)

            if not actual_data.empty:
                # Extract actual calls as a list
                actual_calls = actual_data['calls'].tolist()
                return {"actual_calls": actual_calls}
            else:
                return {"actual_calls": []}
        except Exception as e:
            self.logger.error(f"Error occurred during fetching actual data: {e}")
            return {"error": "Failed to fetch actual data."}

    def analyze_prediction(self, actual_data, predicted_calls):
        try:
            # Calculate mean of actual and predicted calls
            actual_mean = np.mean(actual_data['actual_calls'])
            predicted_mean = np.mean(predicted_calls)

            # Compare means to analyze prediction
            if predicted_mean > actual_mean:
                reason = "The predicted calls are higher than the historical average."
                recommendation = "This could indicate an increase in call volume. Review marketing initiatives or seasonal trends."
            elif predicted_mean < actual_mean:
                reason = "The predicted calls are lower than the historical average."
                recommendation = "This may suggest a decrease in call volume. Investigate factors such as market conditions or customer behavior."
            else:
                reason = "The predicted calls are similar to the historical average."
                recommendation = "Continue monitoring call volume and assess any significant deviations."

            return reason, recommendation
        except Exception as e:
            self.logger.error(f"Error occurred during prediction analysis: {e}")
            return "Error occurred during prediction analysis. Please check the logs."

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            requested_year = request_data.get('year')
            requested_month = request_data.get('month')

            # Train the ensemble model monthly using historical data from 7/10/22 to 31/12/23
            start_date = '2022-10-07'
            end_date = '2023-12-31'
            model = self.train_model_monthly_ensemble(start_date, end_date)

            if model is not None:
                # Predict calls for the requested month
                if requested_month and requested_year:
                    predicted_data = self.predict_calls(int(requested_year), int(requested_month), model)
                    actual_data = self.fetch_actual_data(int(requested_year), int(requested_month))

                    # Analyze predictions
                    reason, recommendation = self.analyze_prediction(actual_data, predicted_data['predicted_calls'])

                    # Construct response data
                    response_data = {
                        "actual_calls": actual_data['actual_calls'],
                        "predicted_calls": predicted_data['predicted_calls'],
                        "reason": reason,
                        "recommendation": recommendation
                    }
                else:
                    response_data = {"error": "Month and year parameters are required."}
            else:
                response_data = {"error": "Model could not be trained."}

            return JsonResponse(response_data, status=200)

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data fetching - {response_data}")
            return JsonResponse(response_data, status=400)


# withut added the reason and recomemendation 
class Idletime(View):
    logger = logging.getLogger(__name__)

    def create_model(self, X_train, y_train, feature_names):
        try:
            # Initialize and train the Random Forest model
            model = RandomForestRegressor(n_estimators=100, random_state=88)
            model.fit(X_train, y_train)
            model.feature_names = feature_names

            return model
        except Exception as e:
            self.logger.error(f"An error occurred while training the model: {e}")
            return None

    def preprocess_data(self, data):
        try:
            # Convert 'Date' column to datetime
            data['Date'] = pd.to_datetime(data['Date'])
                
            # Set 'Date' column as index
            data.set_index('Date', inplace=True)
                
            # Extract features from 'Date'
            data['year'] = data.index.year
            data['month'] = data.index.month
            data['day'] = data.index.day
           
            return data
        except Exception as e:
            self.logger.error(f"Error occurred during data preprocessing: {e}")
            return None

    def train_model_monthly(self, start_date, end_date):
        try:
            # Create database engine
            engine = database()

            # Fetch historical data from the database within the given date range
            historical_data_query = f"""
               SELECT CONVERT(date, timestamp) AS Date, 
       AVG(CAST(idletime AS INT)) AS Average_Idle_Time 
FROM iskillset 
GROUP BY CONVERT(date, timestamp) 
ORDER BY Date ASC;
            """
            historical_data = pd.read_sql(historical_data_query, engine)

            # Preprocess the historical data
            historical_data = self.preprocess_data(historical_data)

            if historical_data is not None:
                # Prepare features and target variable for training
                X = historical_data[['year', 'month', 'day']] 
                y = historical_data['Average_Idle_Time']

                # Get feature names
                feature_names = X.columns.tolist()

                # Initialize and train the Random Forest model
                model = self.create_model(X, y, feature_names)
                return model, X, y
            else:
                return None, None, None
        except Exception as e:
            self.logger.error(f"Error occurred during monthly model training: {e}")
            return None, None, None

    def fetch_actual_data(self, year, month):
        try:
            # Create database engine
            engine = database()

            # Fetch actual data from the database based on user request
            actual_data_query = f"""
                SELECT CONVERT(date, timestamp) AS Date,
                    AVG(CAST(idletime AS INT)) AS Average_Idle_Time 
                FROM iskillset 
                WHERE YEAR(timestamp) = {year} AND MONTH(Timestamp) = {month} 
                GROUP BY CONVERT(date, timestamp) 
                ORDER BY Date ASC
            """
            actual_data = pd.read_sql(actual_data_query, engine)

            return actual_data if not actual_data.empty else pd.DataFrame()  # Return DataFrame or empty DataFrame
        except Exception as e:
            self.logger.error(f"Error occurred during fetching actual data: {e}")
            return pd.DataFrame()  # Return an empty DataFrame in case of an error

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            requested_month = request_data.get('month')
            requested_year = request_data.get('year')

            if requested_month is not None and requested_year is not None:
                # Train the model for the requested month and year
                model, X, y = self.train_model_monthly(requested_year, requested_month)

                if model is not None:
                    # Fetch actual data for the requested month and year
                    actual_data = self.fetch_actual_data(requested_year, requested_month)

                    # Predict idle time for the requested month using the model
                    days_in_month = calendar.monthrange(int(requested_year), int(requested_month))[1]

                    # Predicted idle time for each day of the month
                    predicted_Idletime = []
                    for day in range(1, days_in_month + 1):
                        prediction = model.predict([[int(requested_year), int(requested_month), day]])  
                        predicted_Idletime.append(float(prediction[0]))

                    if not actual_data.empty:
                        # Actual idle time from the database
                        actual_Idletime = actual_data['Average_Idle_Time'].tolist()
                    else:
                        actual_Idletime = []  # Send empty list if no actual data available

                    # Calculate evaluation metrics
                    mae = mean_absolute_error(y, model.predict(X))
                    mse = mean_squared_error(y, model.predict(X))
                    rmse = mean_squared_error(y, model.predict(X), squared=False)

                    # Print evaluation metrics
                    print(f"Mean Absolute Error: {mae}")
                    print(f"Mean Squared Error: {mse}")
                    print(f"Root Mean Squared Error: {rmse}")

                    # Construct response data
                    response_data = {
                        "actual_Idletime": actual_Idletime,
                        "predicted_Idletime": predicted_Idletime,
                        "mae": mae,
                        "mse": mse,
                        "rmse": rmse
                    }
                else:
                    response_data = {"error": "Model could not be trained."}
            else:
                response_data = {"error": "Month and year parameters are required."}

            return JsonResponse(response_data, status=200)

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)

# text to speech using google API
'''import os
import json
import traceback
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework import status
from google.cloud import texttospeech

class TextToSpeech(APIView):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Contact center2/Predivtive_Analysis/loginchatbot-410611-75a2261afa30.json"
        print(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))

    def post(self, request, *args, **kwargs):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            input_text = request_data.get('input', {}).get('text', '')
            language_code = request_data.get('voice', {}).get('languageCode', '')
            voice_name = request_data.get('voice', {}).get('name', '')

            if not input_text:
                return JsonResponse({'error': 'Input text is missing'}, status=status.HTTP_400_BAD_REQUEST)
            if not language_code or not voice_name:
                return JsonResponse({'error': 'Voice parameters are missing'}, status=status.HTTP_400_BAD_REQUEST)

            audio_data = self.text_to_speech_google(input_text, language_code, voice_name)

            # Save audio_data as an MP3 file
            with open('output.mp3', 'wb') as audio_file:
                audio_file.write(audio_data)

            print("Audio file saved successfully.")

            return JsonResponse({'message': 'Audio file saved successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            traceback.print_exc()  # Print the traceback to the console
            return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def text_to_speech_google(self, input_text, language_code, voice_name):
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=input_text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            pitch=0,
            speaking_rate=1
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        return response.audio_content
'''

# text to speech 
class TextToSpeech(APIView):
    def post(self, request, *args, **kwargs):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            text = request_data.get('text', '')
            voice_language = request_data.get('voice', '').lower()  # Convert to lowercase for case-insensitive comparison

            engine = pyttsx3.init()
            voice = engine.getProperty('voices')[0]  # Get the default voice

            # Print information about the default voice
            print("Voice:")
            print(" - ID: %s" % voice.id)
            print(" - Name: %s" % voice.name)
            print(" - Languages: %s" % voice.languages)
            print(" - Gender: %s" % voice.gender)
            print(" - Age: %s" % voice.age)

            if voice_language is None:
                return Response({'error': 'Voice parameter is missing'}, status=status.HTTP_400_BAD_REQUEST)

            if 'english' in voice_language:
                audio_data = self.text_to_speech_pyttsx3(text, 'english')
            else:
                return Response({'error': 'Unsupported voice language'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'audio_data': audio_data.decode('latin-1')}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def text_to_speech_pyttsx3(self, text, language):
        engine = pyttsx3.init()
        engine.setProperty('rate', 141)
        engine.setProperty('volume', 0.9)
        
        output_file = 'output.mp3'
        engine.save_to_file(text, output_file)
        engine.runAndWait()

        # Read the saved audio file and return the audio data
        with open(output_file, 'rb') as file:
            audio_data = file.read()
        
        return audio_data


#added reason and recommendation Handlingtime
class Handing_time(View):
    logger = logging.getLogger(__name__)

    def create_model(self, X_train, y_train, feature_names):
        try:
            # Initialize and train the Random Forest model
            model = RandomForestRegressor(n_estimators=100, random_state=88)
            model.fit(X_train, y_train)
            model.feature_names = feature_names

            return model
        except Exception as e:
            self.logger.error(f"An error occurred while training the model: {e}")
            return None

    def preprocess_data(self, data):
        try:
            # Convert 'Date' column to datetime
            data['Date'] = pd.to_datetime(data['Date'])

            # Set 'Date' column as index
            data.set_index('Date', inplace=True)

            # Extract features from 'Date'
            data['year'] = data.index.year
            data['month'] = data.index.month
            data['day'] = data.index.day

            return data
        except Exception as e:
            self.logger.error(f"Error occurred during data preprocessing: {e}")
            return None

    def train_model_monthly(self, historical_data):
        try:
            if historical_data is not None:
                # Prepare features and target variable for training
                X = historical_data[['year', 'month', 'day']]
                y = historical_data['TotalHandlingTime']

                # Get feature names
                feature_names = X.columns.tolist()

                # Initialize and train the Random Forest model
                model = self.create_model(X, y, feature_names)
                return model, X, y
            else:
                return None, None, None
        except Exception as e:
            self.logger.error(f"Error occurred during monthly model training: {e}")
            return None, None, None

    def fetch_actual_data(self, year, month):
        try:
            # Fetch actual data from the database based on the requested year and month
            actual_data_query = f"""
                SELECT 
                    CAST(OriginatedStamp AS DATE) AS Date,
                    sum(CAST(HandlingTime AS INT)) AS Average_HandlingTime 
                FROM 
                    CustomerCallDetails 
                WHERE 
                    YEAR(OriginatedStamp) = {year} 
                    AND MONTH(OriginatedStamp) = {month} 
                GROUP BY 
                    CAST(OriginatedStamp AS DATE) 
                ORDER BY 
                    Date ASC;
            """
            actual_data = pd.read_sql(actual_data_query, database())

            return actual_data if not actual_data.empty else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error occurred during fetching actual data: {e}")
            return pd.DataFrame()
        
    def analyze_prediction(self, historical_data, predicted_handlingtime):
        try:
            # Calculate mean of actual and predicted handling time
            actual_mean = historical_data['TotalHandlingTime'].mean()
            predicted_mean = np.mean(predicted_handlingtime)

            # Compare means to analyze prediction
            if predicted_mean > actual_mean:
                reason = "The predicted handling time is higher than the historical average."
                recommendation = "This could indicate potential issues in the call handling process. Check for bottlenecks or inefficiencies."
            elif predicted_mean < actual_mean:
                reason = "The predicted handling time is lower than the historical average."
                recommendation = "This may indicate improved efficiency in call handling. Monitor performance to identify any changes."
            else:
                reason = "The predicted handling time is similar to the historical average."
                recommendation = "Continue monitoring performance and consider making adjustments if significant deviations occur."

            return reason, recommendation
        except Exception as e:
            self.logger.error(f"Error occurred during prediction analysis: {e}")
            return "Error occurred during prediction analysis. Please check the logs."

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            requested_month = request_data.get('month')
            requested_year = request_data.get('year')

            if requested_month is not None and requested_year is not None:
                # Fetch historical data for the requested month and year
                historical_data_query = """
                    SELECT 
                        CAST(OriginatedStamp AS DATE) AS Date,
                        SUM(CAST(HandlingTime AS INT)) AS TotalHandlingTime
                    FROM 
                        CustomerCallDetails
                    GROUP BY 
                        CAST(OriginatedStamp AS DATE)
                    ORDER BY 
                        Date ASC;
                """
                historical_data = pd.read_sql(historical_data_query, database())

                # Preprocess the historical data
                historical_data = self.preprocess_data(historical_data)

                # Train the model for the historical data
                model, X, y = self.train_model_monthly(historical_data)

                if model is not None:
                    # Fetch actual data for the requested month and year
                    actual_data = self.fetch_actual_data(requested_year, requested_month)

                    # Predict handling time for the requested month using the model
                    days_in_month = calendar.monthrange(int(requested_year), int(requested_month))[1]

                    # Predicted handling time for each day of the month
                    predicted_handlingtime = []
                    for day in range(1, days_in_month + 1):
                        prediction = model.predict([[int(requested_year), int(requested_month), day]])  
                        predicted_handlingtime.append(float(prediction[0]))

                    if not actual_data.empty:
                        # Actual handling time from the database
                        actual_handlingtime = actual_data['Average_HandlingTime'].tolist()
                    else:
                        actual_handlingtime = []  # Send empty list if no actual data available

                    # Calculate evaluation metrics
                    mae = mean_absolute_error(y, model.predict(X))
                    mse = mean_squared_error(y, model.predict(X))
                    rmse = mean_squared_error(y, model.predict(X), squared=False)

                    # Construct response data
                    response_data = {
                        "actual_handlingtime": actual_handlingtime,
                        "predicted_handlingtime": predicted_handlingtime,
                        "mae": mae,
                        "mse": mse,
                        "rmse": rmse
                    }

                    # Analyze predictions
                    reasons, recommendations = self.analyze_prediction(historical_data, predicted_handlingtime)

                    # Add analysis results to response data
                    response_data["reasons"] = reasons
                    response_data["recommendations"] = recommendations

                else:
                    response_data = {"error": "Model could not be trained."}
            else:
                response_data = {"error": "Month and year parameters are required."}

            return JsonResponse(response_data, status=200)

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)

    
########Added the reason and recommendation 
class Average_Talktime(View):
    logger = logging.getLogger(__name__)

    def create_model(self, X_train, y_train, feature_names):
        try:
            # Initialize and train the Random Forest model
            model = RandomForestRegressor(n_estimators=100, random_state=88)
            print('model', model)
            model.fit(X_train, y_train)
            model.feature_names = feature_names
            print('model1', model)

            return model
        except Exception as e:
            self.logger.error(f"An error occurred while training the model: {e}")
            return None

    def preprocess_data(self, data):
        try:
            # Convert 'Date' column to datetime
            data['Date'] = pd.to_datetime(data['Date'])
                
            # Set 'Date' column as index
            data.set_index('Date', inplace=True)
                
            # Extract features from 'Date'
            data['year'] = data.index.year
            data['month'] = data.index.month
            data['day'] = data.index.day
           
            return data
        except Exception as e:
            self.logger.error(f"Error occurred during data preprocessing: {e}")
            return None

    def train_model_monthly(self, historical_data):
        try:
            if historical_data is not None:
                # Prepare features and target variable for training
                X = historical_data[['year', 'month', 'day']] 
                y = historical_data['Average_TalkTime']

                # Get feature names
                feature_names = X.columns.tolist()

                # Initialize and train the Random Forest model
                model = self.create_model(X, y, feature_names)
                print("model", model)
                print("X", X)
                print("y", y)
                return model, X, y
            else:
                return None, None, None
        except Exception as e:
            self.logger.error(f"Error occurred during monthly model training: {e}")
            return None, None, None

    def fetch_actual_data(self, year, month):
        try:
            # Create database engine
            engine = database()

            # Fetch actual data from the database based on user request
            actual_data_query = f"""
                SELECT 
                    CONVERT(date, AgentActivityDetails.Timestamp) AS Date,
                    SUM(AgentActivityDetails.TalkTime) AS Total_TalkTime,
                    COUNT(*) AS Number_of_Calls,
                    SUM(AgentActivityDetails.TalkTime) / COUNT(*) AS Average_TalkTime
                FROM 
                    AgentActivityDetails 
                WHERE 
                    YEAR(AgentActivityDetails.Timestamp) = {year} 
                    AND MONTH(AgentActivityDetails.Timestamp) = {month} 
                GROUP BY 
                    CONVERT(date, AgentActivityDetails.Timestamp)
                ORDER BY 
                    Date;
            """
            actual_data = pd.read_sql(actual_data_query, engine)

            return actual_data if not actual_data.empty else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error occurred during fetching actual data: {e}")
            return pd.DataFrame()

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            requested_month = request_data.get('month')
            requested_year = request_data.get('year')

            if requested_month is not None and requested_year is not None:
                # Train the model for the requested month and year
                engine = database()
                historical_data_query = """
                    SELECT 
                        CONVERT(date, AgentActivityDetails.Timestamp) AS Date,
                        SUM(AgentActivityDetails.TalkTime) AS Total_TalkTime,
                        COUNT(*) AS Number_of_Calls,
                        SUM(AgentActivityDetails.TalkTime) / COUNT(*) AS Average_TalkTime
                    FROM 
                        AgentActivityDetails 
                    GROUP BY 
                        CONVERT(date, AgentActivityDetails.Timestamp)
                    ORDER BY 
                        Date;
                """
                historical_data = pd.read_sql(historical_data_query, engine)

                # Preprocess the historical data
                historical_data = self.preprocess_data(historical_data)

                # Train the model for the historical data
                model, X, y = self.train_model_monthly(historical_data)

                if model is not None:
                    # Fetch actual data for the requested month and year
                    actual_data = self.fetch_actual_data(requested_year, requested_month)

                    # Predict talk time for the requested month using the model
                    days_in_month = calendar.monthrange(int(requested_year), int(requested_month))[1]

                    # Predicted talk time for each day of the month
                    predicted_talktime = []
                    for day in range(1, days_in_month + 1):
                        prediction = model.predict([[int(requested_year), int(requested_month), day]])  
                        predicted_talktime.append(float(prediction[0]))

                    if not actual_data.empty:
                        # Actual talk time from the database
                        actual_talktime = actual_data['Average_TalkTime'].tolist()
                    else:
                        actual_talktime = []  # Send empty list if no actual data available

                    # Calculate evaluation metrics
                    mae = mean_absolute_error(y, model.predict(X))
                    mse = mean_squared_error(y, model.predict(X))
                    rmse = mean_squared_error(y, model.predict(X), squared=False)

                    # Analyze prediction and provide recommendations
                    reason, recommendation = self.analyze_prediction(historical_data, predicted_talktime)

                    # Construct response data
                    response_data = {
                        "actual_talktime": actual_talktime,
                        "predicted_talktime": predicted_talktime,
                        "mae": mae,
                        "mse": mse,
                        "rmse": rmse,
                        "reason": reason,
                        "recommendation": recommendation
                    }
                else:
                    response_data = {"error": "Model could not be trained."}
            else:
                response_data = {"error": "Month and year parameters are required."}

            return JsonResponse(response_data, status=200)

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)

    def analyze_prediction(self, historical_data, predicted_talktime):
        try:
            # Calculate mean of actual and predicted talk time
            actual_mean = historical_data['Average_TalkTime'].mean()
            predicted_mean = np.mean(predicted_talktime)

            # Compare means to analyze prediction
            if predicted_mean > actual_mean:
                reason = "The predicted talk time is higher than the historical average."
                recommendation = "This could indicate a potential increase in call volume or longer talk times. " \
                                 "Consider allocating more resources or optimizing workflows to handle the anticipated increase."
            elif predicted_mean < actual_mean:
                reason = "The predicted talk time is lower than the historical average."
                recommendation = "This could suggest a decrease in call volume or shorter talk times. " \
                                 "Review staffing levels and evaluate if resources can be reallocated " \
                                 "or if efficiency measures can be implemented."
            else:
                reason = "The predicted talk time is similar to the historical average."
                recommendation = "Continue monitoring performance and consider making adjustments " \
                                 "if significant deviations occur."

            return reason, recommendation
        except Exception as e:
            self.logger.error(f"Error occurred during prediction analysis: {e}")
            return "Error occurred during prediction analysis. Please check the logs."


#Calls per agent added reason and recommendation 
class Calls_per_Agent(View):
    logger = logging.getLogger(__name__)

    def create_model(self, X_train, y_train, feature_names):
        try:
            # Initialize and train the Random Forest model
            model = RandomForestRegressor(n_estimators=100, random_state=88)
            model.fit(X_train, y_train)
            model.feature_names = feature_names

            return model
        except Exception as e:
            self.logger.error(f"An error occurred while training the model: {e}")
            return None

    def preprocess_data(self, data):
        try:
            # Convert 'Date' column to datetime
            data['Date'] = pd.to_datetime(data['Date'])
                
            # Set 'Date' column as index
            data.set_index('Date', inplace=True)
                
            # Extract features from 'Date'
            data['year'] = data.index.year
            data['month'] = data.index.month
            data['day'] = data.index.day
            
           
            return data
        except Exception as e:
            self.logger.error(f"Error occurred during data preprocessing: {e}")
            return None

    def train_model_daily(self, historical_data):
        try:
            if historical_data is not None:
                # Prepare features and target variable for training
                X = historical_data[['year', 'month', 'day']] 
                y = historical_data['Calls_per_Agent']

                # Get feature names
                feature_names = X.columns.tolist()

                # Initialize and train the Random Forest model
                model = self.create_model(X, y, feature_names)
                return model, X, y
            else:
                return None, None, None
        except Exception as e:
            self.logger.error(f"Error occurred during daily model training: {e}")
            return None, None, None

    def fetch_actual_data(self, requested_year, requested_month):
        try:
            # Create database engine
            engine = database()

            # Fetch actual data from the database based on user request
            actual_data_query = f"""
                SELECT 
                    CAST(Timestamp AS DATE) AS Date,
                    COUNT(*) AS Number_of_Calls,
                    COUNT(DISTINCT AgentGivenName) AS Number_of_Agents,
                    CASE 
                        WHEN COUNT(DISTINCT AgentGivenName) = 0 THEN 0 
                        ELSE COUNT(*) / COUNT(DISTINCT AgentGivenName) 
                    END AS Calls_per_Agent
                FROM 
                    AgentActivityDetails 
                WHERE 
                    YEAR(Timestamp) = {requested_year} 
                    AND MONTH(Timestamp) = {requested_month} 
                GROUP BY 
                    CAST(Timestamp AS DATE)
                ORDER BY 
                    Date;
            """
            actual_data = pd.read_sql(actual_data_query, engine)

            return actual_data if not actual_data.empty else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error occurred during fetching actual data: {e}")
            return pd.DataFrame()

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            requested_month = request_data.get('month')
            requested_year = request_data.get('year')

            if requested_month is not None and requested_year is not None:
                # Train the model for the requested month and year
                engine = database()

                # Fetch historical data from the database
                historical_data_query = """
                    SELECT 
                        CAST(Timestamp AS DATE) AS Date,
                        COUNT(*) AS Number_of_Calls,
                        COUNT(DISTINCT AgentGivenName) AS Number_of_Agents,
                        CASE 
                            WHEN COUNT(DISTINCT AgentGivenName) = 0 THEN 0 
                            ELSE COUNT(*) / COUNT(DISTINCT AgentGivenName) 
                        END AS Calls_per_Agent
                    FROM 
                        AgentActivityDetails
                    GROUP BY 
                        CAST(Timestamp AS DATE)
                    ORDER BY 
                        Date;
                """
                historical_data = pd.read_sql(historical_data_query, engine)

                # Preprocess the historical data
                historical_data = self.preprocess_data(historical_data)

                # Train the model for the historical data
                model, X, y = self.train_model_daily(historical_data)

                if model is not None:
                    # Fetch actual data
                    actual_data = self.fetch_actual_data(requested_year, requested_month)

                    # Predict calls per agent for the requested month using the model
                    days_in_month = calendar.monthrange(int(requested_year), int(requested_month))[1]

                    # Predicted calls per agent for each day of the month
                    predicted_calls_per_agent = []
                    for day in range(1, days_in_month + 1):
                        prediction = model.predict([[int(requested_year), int(requested_month), day]])  
                        predicted_calls_per_agent.append(float(prediction[0]))

                    if not actual_data.empty:
                        # Actual calls per agent from the database
                        actual_calls_per_agent = actual_data['Calls_per_Agent'].tolist()
                    else:
                        actual_calls_per_agent = []  # Send empty list if no actual data available

                    # Calculate evaluation metrics
                    mae = mean_absolute_error(y, model.predict(X))
                    mse = mean_squared_error(y, model.predict(X))
                    rmse = mean_squared_error(y, model.predict(X), squared=False)

                    # Analyze prediction and provide recommendations
                    reason, recommendation = self.analyze_prediction(historical_data, predicted_calls_per_agent)

                    # Construct response data
                    response_data = {
                        "actual_calls_per_agent": actual_calls_per_agent,
                        "predicted_calls_per_agent": predicted_calls_per_agent,
                        "mae": mae,
                        "mse": mse,
                        "rmse": rmse,
                        "reason": reason,
                        "recommendation": recommendation
                    }
                else:
                    response_data = {"error": "Model could not be trained."}
            else:
                response_data = {"error": "Month and year parameters are required."}

            return JsonResponse(response_data, status=200)

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)
    

    


    def analyze_prediction(self, historical_data, predicted_calls_per_agent):
        try:
            # Calculate mean of actual and predicted calls per agent
            actual_mean = historical_data['Calls_per_Agent'].mean()
            predicted_mean = np.mean(predicted_calls_per_agent)

            # Compare means to analyze prediction
            if predicted_mean > actual_mean:
                reason = "The predicted calls per agent is higher than the historical average."
                recommendation = "This could indicate a potential increase in workload per agent. " \
                                 "Consider reviewing staffing levels or workload distribution to ensure optimal performance."
            elif predicted_mean < actual_mean:
                reason = "The predicted calls per agent is lower than the historical average."
                recommendation = "This could suggest a decrease in workload per agent. " \
                                 "Evaluate staffing levels and workload distribution to avoid overstaffing " \
                                 "or identify areas where additional support may be needed."
            else:
                reason = "The predicted calls per agent is similar to the historical average."
                recommendation = "Continue monitoring workload per agent and make adjustments as necessary " \
                                 "based on observed trends and performance metrics."

            return reason, recommendation
        except Exception as e:
            self.logger.error(f"Error occurred during prediction analysis: {e}")
            return "Error occurred during prediction analysis. Please check the logs.", ""


#connect to db and fetch the column name 
class Attribute(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            name = request_data.get("DB_name")
            host = request_data.get("server_name")
            user = request_data.get("User_name")
            password = request_data.get("Password")
            table_name = request_data.get("Table_name")

            print("Extracted request data successfully")

            engine = create_engine(f'mssql+pyodbc://{user}:{password}@{host}/{name}?driver=ODBC+Driver+17+for+SQL+Server')

            print("Database connection established",engine)

            
            print("Hello1")
            

            print("Database details stored in session")

            # Connecting to the database
            metadata = MetaData()
            metadata.reflect(bind=engine)
            table = metadata.tables.get(table_name)

            if table is None:
                return JsonResponse({"error": f"Table '{table_name}' not found in the database."}, status=404)

            columns = [column.name for column in table.columns]

            print("columns", columns)
            '''request.session['db_details'] = {
                'name': name,
                'host': host,
                'user': user,
                'password': password,
                'table_name': table_name
            }'''
            
            print("HEllo2")
            # "print("request", request.session.get('db_details'))"

            print("Column names retrieved from the database")

            return JsonResponse({"columns": columns})

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            print(response_data)
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)


# save  the db_name server name username, password, table name UI side
class Add_Column(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            # Extract column name from the request
            request_data = json.loads(request.body.decode('utf-8'))
            # name = request_data.get("DB_name")
            # host = request_data.get("server_name")
            # user = request_data.get("User_name")
            # password = request_data.get("Password")

            name = "CognicxContextCentre_AWS"
            host = "DESKTOP-21ATSCV"
            user = "sa"
            password = "sa123"
            table_name = "CustomerCallDetails"
            column_name = request_data.get("column_name")

            print("column_name", column_name)
            if not column_name:
                return JsonResponse({"error": "Column name not provided in the request."}, status=400)

            # Connect to the MSSQL server using SQLAlchemy with pyodbc driver
            engine = create_engine(f'mssql+pyodbc://{user}:{password}@{host}/{name}?driver=ODBC+Driver+17+for+SQL+Server')

            # Construct the SQL statement to add a column to the table
            sql_statement = text(f"ALTER TABLE {table_name} ADD [{column_name}] VARCHAR(255)")
            # sql_statement = text(f"ALTER TABLE {table_name} ADD [{column_name}] VARCHAR(255)")

            # Execute the SQL statement
            with engine.connect() as conn:
                conn.execute(sql_statement)
                conn.commit()
                conn.close()

            column_name = request_data.get("column_name")
            st = "inactive"
            Description = "Plese Add the discrption"
            engine = database()
            conn = engine.connect()
            conn.execute(
                text('''INSERT INTO Attributecolumn ([column_name], [Description], [Status]) VALUES (:column_name, :description, :status)'''), 
                {"column_name": column_name, "status": st, "description": Description}
            )
            conn.commit()
            conn.close()

            # Return success response
            return JsonResponse({"message": f"Column '{column_name}' added to table '{table_name}' successfully."})

        except Exception as e:
            error_message = str(e)
            response_data = {'error': error_message}
            self.logger.warning(f"Error during data processing - {response_data}")
            return JsonResponse(response_data, status=400)


class Add_Formula(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            Formula = request_data.get("formula")
            status = "Inactive"
            Description = "Condition is for the given Formuls"
            print("Received formula:", Formula)  # Debug: Print the received formula
            Table_name = request_data.get("tableName")
            print("Table, Name", Table_name)# take the table name in request in future

            # Remove space between two numbers in the formula
            Formula = self.remove_space_between_numbers(Formula)

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Insert the formula and MSSQL query into the database
            # conn.execute(text('''INSERT INTO rules (Formula, status, Description, Query) VALUES (?,?,?,? )'''),{"formula": Formula, "status": status, "Description": Description })
            # conn.execute(text('''INSERT INTO rules (Formula, Query) VALUES (:formula, NULL)'''), {"formula": Formula})

            conn.execute(text('''INSERT INTO rules (Formula, status, Description, Query) VALUES (:formula, :status, :description, NULL)'''), {"formula": Formula, "status": status, "description": Description})

            # Commit the transaction
            conn.commit()

            conn.execute(text('''EXEC [dbo].[ConvertFormulasToQueries] @TableName = :TableName, @formula = :formula'''), {"TableName": Table_name, "formula": Formula})
            # pass the table name in request also update the procedure 
            conn.commit()

            # Close the connection
            conn.close()

            print("Formula submitted successfully")

            return JsonResponse({"message": "Formula added successfully"}, status=200)
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    def remove_space_between_numbers(self, formula):
        # Regular expression to find patterns like "<digit> <digit>"
        pattern = r'(\d+)\s+(\d+)'
        # Replace such patterns with "<digit><digit>"
        formula = re.sub(pattern, r'\1\2', formula)
        # Handling the case where a digit comes before a comparison operator and another digit
        pattern = r'(\d+)\s*([><=])\s*(\d+)'
        # Replace such patterns with "<digit><comparison_operator><digit>"
        formula = re.sub(pattern, r'\1\2\3', formula)
        # Handling the case where digits are grouped together without any operator between them
        pattern = r'(\d+)\s+(\d+)(?=\s|$)'
        # Replace such patterns with "<digit><digit>"
        formula = re.sub(pattern, r'\1\2', formula)
        return formula


# group rules
def database1():
    NAME = 'CognicxContextCentre_AWS'
    HOST = 'DESKTOP-21ATSCV'
    USER = 'sa'
    PASSWORD = 'sa123'
    connection_string = f'DRIVER=SQL Server; SERVER={HOST};DATABASE={NAME};UID={USER};PWD={PASSWORD};'
    conn = pyodbc.connect(connection_string)
    return conn  
        
# creating a group of query 
class GroupRules(View):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            # Load request data
            request_data = json.loads(request.body.decode('utf-8'))
            query_group = request_data.get("query_group")
            recommendation = request_data.get("recommendation")
            st = "Inactive" #status
            Description = "Condition is for the given Formuls"
            print("query_group", query_group)
            print("recommendation", recommendation)
            Notification_time = "2024-01-01 00:00:00"


            if not all([query_group, recommendation]):
                response_data = {
                    'responseMessage': 0,
                    'responseCode': 400,
                    'data': [],
                    'error': 'Missing one or more mandatory fields'
                }
                self.logger.warning(f"Missing mandatory fields in the request - {response_data}")
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # Split query_group into individual query IDs and logical operators
            query_parts = query_group.split()
            query_ids = []
            logical_operators = []
            for part in query_parts:
                if part.isdigit():
                    query_ids.append(int(part))
                elif part.upper() in ['AND', 'OR', 'NOT']:
                    logical_operators.append(part.upper())

            print("query_ids", query_ids)
            print("logical_operators", logical_operators)

            # Fetch formulas from the database for each query ID
            conn = database1()  # Establish database connection using your method
            cursor = conn.cursor()
            formulas = []

            for query_id in query_ids:
                cursor.execute("SELECT Formula FROM rules WHERE Query_ID = ?", (query_id,))
                formula = cursor.fetchone()[0]
                formulas.append(formula)

            print("formulas", formulas)

            # Construct SQL query
            sql_query = "SELECT * FROM CustomerCallDetails WHERE "
            for i, formula in enumerate(formulas):
                # Remove square brackets
                formula = formula.replace("[", "").replace("]", "")
                sql_query += formula
                if i < len(logical_operators) and i + 1 < len(formulas):
                    sql_query += f" {logical_operators[i]} "

            print("sql_query",sql_query)

            # Insert query_group into group_rules table
            cursor.execute("INSERT INTO group_rules (query_group, recommendation, status, description, Notification_time) VALUES (?, ?, ?, ?, ?)", (sql_query, recommendation, st, Description, Notification_time))
            conn.commit()

            # Close database connection
            conn.close()

            return JsonResponse({"success": "SQL query inserted successfully."}, status=200)

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            self.logger.error(error_message)
            return JsonResponse({"error": error_message}, status=500)


# Recommendation where 
class Recommendation(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Fetch recommendations where result is True
            result = conn.execute(text('''SELECT recommendation, Query_ID FROM group_rules WHERE result = :result'''), {"result": True})

            # Extract query IDs and recommendations from the result set
            query_ids = []
            recommendations = []
            for row in result.fetchall():
                query_ids.append(row[1])
                recommendations.append(row[0])

            print("recommendations", recommendations)
            
            # Close the database connection
            conn.close()

            # Construct the response data
            response_data = {
                "Query_ID": query_ids,
                "recommendations": recommendations
            }

            # Send response with recommendations
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Home page API
class Home_page(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Fetch recommendations where result is True
            recommendation = conn.execute(text('''SELECT Query_ID, recommendation, description, status FROM group_rules '''))
            recommendation_data = []
            for row in recommendation.fetchall():
                recommendation_data.append({
                    "ID": row[0],
                    "recommendation": row[1],
                    "description": row[2],
                    "status": row[3]
                })

            # Fetch formulas
            formula = conn.execute(text('''SELECT Query_ID, Formula, description, status FROM rules '''))
            formula_data = []
            for row in formula.fetchall():
                formula_data.append({
                    "ID": row[0],
                    "Formula": row[1],
                    "description": row[2],
                    "status": row[3]
                })

            # Fetch column names from AgentActivityDetails table
            attribute = conn.execute(text('''SELECT ID, column_name, Description, status FROM Attributecolumn '''))
            attribute_data = []
            for row in attribute.fetchall():
                attribute_data.append({
                    "ID": row[0],
                    "column_name": row[1],
                    "description": row[2],
                    "status": row[3]
                })

            # Close the database connection
            conn.close()

            # Construct the response data
            response_data = {
                "Attribute": attribute_data,
                "Formula": formula_data,
                "Recommendation": recommendation_data
            }

            # Send response with recommendations
            #print(response_data)
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Active in active status for attribute table
class Attribute_status_Update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Check the current status in the database
            current_status = conn.execute(text("SELECT status FROM Attributecolumn WHERE ID = :ID"), {"ID": a}).fetchone()
            print("current_status", current_status)
            if current_status is None:
                # If there is no record with the given ID, return an error response
                conn.close()
                return Response({"error": f"No record found with ID {a}"}, status=status.HTTP_404_NOT_FOUND)

            # Toggle the status
            new_status = "Inactive" if current_status[0] == "Active" else "Active"

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE Attributecolumn SET status = :status WHERE ID = :ID')
            conn.execute(query, {"status": new_status, "ID": a})
            conn.commit()
            conn.close()

            print("Status updated successfully")
            return Response({"message": f"Status updated to {new_status} successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# active inactive status for formula (SCENARIO)
class Formula_status_Update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Check the current status in the database
            current_status = conn.execute(text("SELECT status FROM rules WHERE Query_ID = :ID"), {"ID": a}).fetchone()
            print("current_status", current_status)
            if current_status is None:
                # If there is no record with the given ID, return an error response
                conn.close()
                return Response({"error": f"No record found with ID {a}"}, status=status.HTTP_404_NOT_FOUND)

            # Toggle the status
            new_status = "Inactive" if current_status[0] == "Active" else "Active"

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE rules SET status = :status WHERE Query_ID = :ID')
            conn.execute(query, {"status": new_status, "ID": a})
            conn.commit()
            conn.close()

            print("Status updated successfully")
            return Response({"message": f"Status updated to {new_status} successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#active inactive status for Remmendation 
class Recommendation_status_Update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Check the current status in the database
            current_status = conn.execute(text("SELECT status FROM group_rules WHERE Query_ID = :ID"), {"ID": a}).fetchone()
            print("current_status", current_status)
            if current_status is None:
                # If there is no record with the given ID, return an error response
                conn.close()
                return Response({"error": f"No record found with ID {a}"}, status=status.HTTP_404_NOT_FOUND)

            # Toggle the status
            new_status = "Inactive" if current_status[0] == "Active" else "Active"

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE group_rules SET status = :status WHERE Query_ID = :ID')
            conn.execute(query, {"status": new_status, "ID": a})
            conn.commit()
            conn.close()

            print("Status updated successfully")
            return Response({"message": f"Status updated to {new_status} successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#update the description in Attribute table 
class Attribute_Description_update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")
            Description = request_data.get("Description")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE Attributecolumn SET Description = :Description WHERE ID = :ID')
            conn.execute(query, {"ID": a, "Description": Description})
            conn.commit()
            conn.close()

            print("Description", Description)
            print(f"Description updated successfully")
            return Response({"message": f"Description updated to successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            self.logger.error(f"An error occurred: {(str(e))}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Discription update of formula
class Formula_Description_update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")
            Description = request_data.get("Description")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE Rules SET Description = :Description WHERE Query_ID = :Query_ID')
            conn.execute(query, {"Query_ID": a, "Description": Description})
            conn.commit()
            conn.close()

            print("Description", Description)
            print(f"Description updated successfully")
            return Response({"message": f"Description updated to successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            self.logger.error(f"An error occurred: {(str(e))}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
#Discription update of Group_Query(Recommendation)
class Recommendation_Description_update(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            a = request_data.get("ID")
            Description = request_data.get("Description")

            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            # Update the status in the database using SQLAlchemy text construct
            query = text('UPDATE group_rules SET Description = :Description WHERE Query_ID = :Query_ID')
            conn.execute(query, {"Query_ID": a, "Description": Description})
            conn.commit()
            conn.close()

            print("Description", Description)
            print(f"Description updated successfully")
            return Response({"message": f"Description updated to successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            self.logger.error(f"An error occurred: {(str(e))}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# showing the formula table 
class Formula_Show(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            engine = database()  # Assuming this function establishes the database connection
            conn = engine.connect()

            formula = conn.execute(text('''SELECT Query_ID, Formula FROM rules '''))
            formula_data = []
            for row in formula.fetchall():
                formula_data.append({
                    "ID": row[0],
                    "Formula": row[1]
                })
            print("formula_data send Succeessfully", formula_data)
            return Response(formula_data, status=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Web design of home Page
def Prediction(request):
    return  render (request, 'prediction.html')

def home(request):
    return  render (request, 'home.html')

def dbconnect(request):
    return render(request, 'dbconnect.html')

def formula(request):
    return  render (request, 'Formul.html')


class Snooze_notification(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            Recommendation = request_data.get("Recommendation")
            print("Recommendation", Recommendation)
            engine = database()
            conn = engine.connect()
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            query = text("UPDATE group_rules SET notification_time = :current_datetime WHERE Recommendation = :Recommendation AND Result = 'True'")
            conn.execute(query, {"current_datetime": current_datetime, "Recommendation": Recommendation})
            conn.commit()
            print("Notification Time updated Successfully")
            conn.close()
            return JsonResponse("Notification Time updated Successfully", status=status.HTTP_200_OK, safe=False)
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            print(error_message)  # Print to console for debugging
            self.logger.error(error_message)
            return JsonResponse("Error occurred while sending notifications", status=status.HTTP_500_INTERNAL_SERVER_ERROR, safe=False)


#code for notification
def send_notification(registration_ids, message_title, message_desc, include_snooze=False):
    try:
        fcm_api = "AAAAzCBYKnU:APA91bF8RHFrIq4Nb5iIoJmUStjKRjfeEgAFzUfUwffHCTuZS-A6JWgdcaEroNxXRg7S4mqnszDPBxTzB68cL_xsIkAw2HW8GIbJx-MDVEDtDJD_q44ZQpDSoqhiYta3NYprs3NmMHrp"
        url = "https://fcm.googleapis.com/fcm/send"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": 'key=' + fcm_api
        }

        # Only include the necessary data payload
        data_payload = {
            "title": message_title,
            "body": message_desc,
            "image": "https://www.cognicx.com/wp-content/uploads/logo-1.png",
            "click_action": "https://www.google.com/search?q=ipl+today+match&oq=&gs_lcrp=EgZjaHJvbWUqCQgAECMYJxjqAjIJCAAQIxgnGOoCMgkIARAjGCcY6gIyCQgCECMYJxjqAjIJCAMQIxgnGOoCMgkIBBAjGCcY6gIyCQgFECMYJxjqAjIJCAYQIxgnGOoCMgkIBxAjGCcY6gLSAQoxMjA0NjJqMGo3qAIIsAIB&sourceid=chrome&ie=UTF-8",
            "icon": "https://www.shutterstock.com/image-vector/letter-r-logo-260nw-308667314.jpg",
            "include_snooze": "true" if include_snooze else "false"
        }

        payload = {
            "registration_ids": registration_ids,
            "priority": "high",
            "data": data_payload
        }

        #print("Sending payload: ", json.dumps(payload, indent=2))  # Debugging line

        result = requests.post(url, data=json.dumps(payload), headers=headers)
        
        response_data = result.json()
        print("FCM Response:", response_data)  # Debugging line
    except json.JSONDecodeError as e:
        error_message = f"An error occurred: {str(e)}"
        print(error_message)  
        
        print("Failed to decode JSON response:", error_message)
        print("Response text:", result.text)


class Send(APIView):
    logger = logging.getLogger(__name__)

    def post(self, request):
        try:
            engine = database()
            conn = engine.connect()

            # Retrieve tokens from the Notification table
            query = text('SELECT Token FROM notification')
            result = conn.execute(query)
            tokens = [row[0] for row in result]
            cutoff_datetime = datetime.now() - timedelta(hours=1)

            # Get recommendations with Result=True from the group_rules table
            query_recommendations = text('''
                SELECT recommendation 
                FROM group_rules 
                WHERE Result = 'True' 
                AND notification_time < :cutoff_datetime
            ''')
            result_recommendations = conn.execute(query_recommendations, {'cutoff_datetime': cutoff_datetime})
            recommendations = [row[0] for row in result_recommendations]

            print("Recommendations retrieved: ", recommendations)  # Debugging line

            # Send notifications for each recommendation to all tokens
            if recommendations:
                # # Only send the first recommendation with the snooze button
                for recommendation in recommendations:
                    send_notification(tokens, 'Recommendation', recommendation, include_snooze=True)

            conn.commit()
            conn.close()

            self.logger.info("Notifications sent successfully")
            return JsonResponse("Notifications sent", status=status.HTTP_200_OK, safe=False)

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            print(error_message)
            self.logger.error(error_message)
            return JsonResponse("Error occurred while sending notifications", status=status.HTTP_500_INTERNAL_SERVER_ERROR, safe=False)


def showFirebaseJS(request):
    data = '''
        importScripts('https://www.gstatic.com/firebasejs/8.6.3/firebase-app.js');
        importScripts('https://www.gstatic.com/firebasejs/8.6.3/firebase-messaging.js');

        var firebaseConfig = {
            apiKey: "AIzaSyDmtXy5d4d8O2kMx8gq3bpq6t49yJRwTng",
            authDomain: "recommendation-analysis-9d5ef.firebaseapp.com",
            projectId: "recommendation-analysis-9d5ef",
            storageBucket: "recommendation-analysis-9d5ef.appspot.com",
            messagingSenderId: "876715977333",
            appId: "1:876715977333:web:57487268ea326cfcae263c",
            measurementId: "G-WDGP80L30F"
        };

        firebase.initializeApp(firebaseConfig);
        const messaging = firebase.messaging();

        messaging.onBackgroundMessage(function(payload) {
            console.log('[firebase-messaging-sw.js] Received background message ', payload);

            const notificationTitle = payload.data.title;
            const notificationOptions = {
                body: payload.data.body,
                icon: payload.data.icon,
                image: payload.data.image,
                click_action: payload.data.click_action,
                tag: "unique_tag_" + payload.data.body.slice(0, 10),  // Generate a unique tag
                data: {
                    recommendation: payload.data.body
                }
            };

            // Conditionally add snooze action if include_snooze flag is true
            if (payload.data.include_snooze === "true") {
                notificationOptions.actions = [
                    {
                        action: 'snooze',
                        title: 'Snooze For 1 Hours'
                    }
                ];
            }

            // Show the notification using the unique tag
            self.registration.showNotification(notificationTitle, notificationOptions);
        });

        self.addEventListener('notificationclick', function(event) {
            console.log('On notification click: ', event.notification);
            if (event.action === 'snooze') {
                const recommendation = event.notification.data.recommendation;
                event.waitUntil(
                    fetch('http://127.0.0.1:8000/Snooze_notification/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ "Recommendation": recommendation })
                    })
                    .then(function(response) {
                        if (response.ok) {
                            console.log('Snooze request sent successfully.');
                        } else {
                            console.error('Failed to send snooze request.');
                        }
                    })
                    .catch(function(error) {
                        console.error('Error sending snooze request:', error);
                    })
                );
            } else {
                clients.openWindow(event.notification.data.click_action);
            }
            event.notification.close();
        });





    '''

    return HttpResponse(data, content_type="text/javascript")



logger = logging.getLogger(__name__)

class Store_token(View):
    

    def post(self, request):
        try:
            request_data = json.loads(request.body.decode("utf-8"))
            Token = request_data.get('Token')
            print("Token", Token)
            logger.info("Token received: %s", Token)

            engine = database() # Update this with your actual database connection
            conn = engine.connect()

            conn.execute(text('''EXEC UpsertNotification @Token=:Token'''), {"Token": Token})
            conn.commit()
            print("Token successfully inserted")
            logger.info("Token successfully inserted")

            return JsonResponse({"message": "Token Inserted successfully"}, status=200)

        except Exception as e:
            logger.error("An error occurred: %s", e, exc_info=True)
            return JsonResponse({"error": "An error occurred"}, status=500)


# schduler 
#Uncomment the below code to start the sceduler 

# import pyodbc
# import threading
# import time
# import requests
# from datetime import datetime, timedelta

# def database1():
#     NAME = 'CognicxContextCentre_AWS'
#     HOST = 'DESKTOP-21ATSCV'
#     USER = 'sa'
#     PASSWORD = 'sa123'
#     connection_string = f'DRIVER=SQL Server; SERVER={HOST};DATABASE={NAME};UID={USER};PWD={PASSWORD};'
#     conn = pyodbc.connect(connection_string)
#     return conn

# def execute_query(conn):
#     try:
#         cursor = conn.cursor()
#         # 1. Execute query to fetch query_group and notification_time from group_rules
#         cursor.execute("SELECT query_group, notification_time FROM group_rules")
#         rows = cursor.fetchall()

#         print("Executing queries")

#         update_queries = []
#         api_call_required = False

#         for row in rows:
#             query_group, notification_time = row
#             cursor.execute(query_group)
#             query_result = cursor.fetchone()

#             # Check if data is fetched
#             result = 'False' if query_result else 'True'
#             # Prepare update queries
#             update_queries.append((result, query_group))

#             # Check if the API needs to be called
#             if result == 'True' and (notification_time is None or notification_time < datetime.now() - timedelta(minutes=2)):
#                 api_call_required = True

#         # Execute update queries
#         for result, query_group in update_queries:
#             cursor.execute("UPDATE group_rules SET result = ? WHERE query_group = ?", (result, query_group))

#         if api_call_required:
#             print("Time difference greater than 2 minutes. Calling API...")

#             try:
#                 # Call the API with a timeout
#                 response = requests.post('http://127.0.0.1:8000/Send/', json={}, timeout=10)
#                 if response.status_code == 200:
#                     print("API call successful")
#                     # Update notification_time to current time for all rows that triggered the API call
#                     current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#                     for result, query_group in update_queries:
#                         if result == 'True':
#                             cursor.execute("UPDATE group_rules SET notification_time = ? WHERE query_group = ?", (current_datetime, query_group))
#                     conn.commit()
#                     print("Notification Time updated successfully. Same notification can come after 2 minutes")
#                 else:
#                     print(f"API call failed with status code: {response.status_code}")
#                     print(f"Response: {response.text}")
#             except requests.RequestException as e:
#                 print(f"API call exception: {e}")

#         conn.commit()
#         cursor.close()
#     except Exception as e:
#         print(f"An error occurred: {str(e)}")

# def run_query_scheduler():
#     conn = database1()
#     while True:
#         print("Scheduler is running")
#         execute_query(conn)
#         time.sleep(90)  # Sleep for 30 seconds after each execution
#         print("Scheduler running again after 30 seconds")

# # Start the query scheduler in a separate thread
# scheduler_thread = threading.Thread(target=run_query_scheduler)
# scheduler_thread.start()
