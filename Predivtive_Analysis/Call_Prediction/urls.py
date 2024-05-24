from django.urls import path
from Call_Prediction.views import *
from . import views

urlpatterns = [
    path('CallsPredictJson/', CallsPredictJson.as_view(), name='CallsPredictJson'),
    path('Show_Column/', Show_Column.as_view(), name='Show_Column'),
    path('Update_Rules/', Update_Rules.as_view(), name='Update_Rules'),
    path('FormulaStandardFormula/', FormulaStandardFormula.as_view(), name='FormulaStandardFormula'),
    path('Idletime/', Idletime.as_view(), name='Idletime'),
    path('TextToSpeech/', TextToSpeech.as_view(), name='TextToSpeech'),
    path('Average_Talktime/', Average_Talktime.as_view(), name='Average_Talktime'),
    path('Handing_time/', Handing_time.as_view(), name='Handing_time'),
    path('Calls_per_Agent/', Calls_per_Agent.as_view(), name='Calls_per_Agent'),
    path('Attribute/', Attribute.as_view(), name='Attribute'),
    path('Add_Column/', Add_Column.as_view(), name='Add_Column'),
    path('Add_Formula/', Add_Formula.as_view(), name='Add_Formula'),
    path('GroupRules/', GroupRules.as_view(), name='GroupRules'),
    path('Recommendation/', Recommendation.as_view(), name='Recommendation'),
    path('Home_page/', Home_page.as_view(), name='Home_page'),
    
    path('Attribute_status_Update/', Attribute_status_Update.as_view(), name='Attribute_status_Update'),
    path('Formula_status_Update/', Formula_status_Update.as_view(), name='Formula_status_Update'),
    path('Recommendation_status_Update/', Recommendation_status_Update.as_view(), name='Recommendation_status_Update'),

    path('Attribute_Description_update/', Attribute_Description_update.as_view(), name='Attribute_Description_update'),
    path('Formula_Description_update/', Formula_Description_update.as_view(), name='Formula_Description_update'),
    path('Recommendation_Description_update/', Recommendation_Description_update.as_view(), name='Recommendation_Description_update'),

    path('Formula_Show/', Formula_Show.as_view(), name='Formula_Show'),
    path('', views.Prediction, name='Pediction'),
    path('Home.html', views.home, name='Home_Page'),
    path('dbconnect.html', views.dbconnect, name='DBconnect'),
    path('formul.html', views.formula, name='formula'),
    #path('send/' , send),
    path('firebase-messaging-sw.js',showFirebaseJS,name="show_firebase_js"),
    path('Store_token/', Store_token.as_view(), name='Store_token'),
    path('Snooze_notification/', Snooze_notification.as_view(), name='Snooze_notification'),
    path('Send/', Send.as_view(), name='Send'),


]