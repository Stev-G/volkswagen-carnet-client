#!/usr/bin/python
# Script to emulate VW CarNet web site
# Author  : Rene Boer
# Version : 1.0
# Date    : 5 Jan 2018
# Original source: https://github.com/reneboer/python-carnet-client/
# Free for use & distribution

import re
import requests
import json
import sys
from urlparse import urlsplit

# import libraries
import lib_mqtt as MQTT

DEBUG = False
#DEBUG = True

MQTT_TOPIC_IN = "/carnet/#"
MQTT_TOPIC = "/carnet"
MQTT_QOS = 0


# Login information for the VW CarNet website
CARNET_USERNAME = ''
CARNET_PASSWORD = ''
CARNET_SPIN = ''

HEADERS = { 'Accept': 'application/json, text/plain, */*',
			'Content-Type': 'application/json;charset=UTF-8',
			'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; D5803 Build/23.5.A.1.291; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/63.0.3239.111 Mobile Safari/537.36' }

def CarNetLogin(s,email, password):
	AUTHHEADERS = { 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
			'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; D5803 Build/23.5.A.1.291; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/63.0.3239.111 Mobile Safari/537.36' }
	auth_base = "https://security.volkswagen.com"
	base = "https://www.volkswagen-car-net.com"

	# Regular expressions to extract data
	csrf_re = re.compile('<meta name="_csrf" content="([^"]*)"/>')
	redurl_re = re.compile('<redirect url="([^"]*)"></redirect>')
	viewstate_re = re.compile('name="javax.faces.ViewState" id="j_id1:javax.faces.ViewState:0" value="([^"]*)"')
	authcode_re = re.compile('code=([^"]*)&')
	authstate_re = re.compile('state=([^"]*)')
    
	def extract_csrf(r):
		return csrf_re.search(r.text).group(1)

	def extract_redirect_url(r):
		return redurl_re.search(r.text).group(1)

	def extract_view_state(r):
		return viewstate_re.search(r.text).group(1)

	def extract_code(r):
		return authcode_re.search(r).group(1)

	def extract_state(r):
		return authstate_re.search(r).group(1)

	# Request landing page and get CSFR:
	r = s.get(base + '/portal/en_GB/web/guest/home')
	if r.status_code != 200:
		return ""
	csrf = extract_csrf(r)
	#print(csrf)
	
	# Request login page and get CSRF
	AUTHHEADERS["Referer"] = base + '/portal'
	AUTHHEADERS["X-CSRF-Token"] = csrf
	r = s.post(base + '/portal/web/guest/home/-/csrftokenhandling/get-login-url',headers=AUTHHEADERS)
	if r.status_code != 200:
		return ""
	responseData = json.loads(r.content)
	lg_url = responseData.get("loginURL").get("path")
	#print(lg_url)
	# no redirect so we can get values we look for
	r = s.get(lg_url, allow_redirects=False, headers=AUTHHEADERS)
	if r.status_code != 302:
		return ""
	ref_url = r.headers.get("location")
	#print(ref_url)
	
	# now get actual login page and get session id and ViewState
	r = s.get(ref_url, headers=AUTHHEADERS)
	if r.status_code != 200:
		return ""
	view_state = extract_view_state(r)
	#print(view_state)

	# Login with user details
	AUTHHEADERS["Faces-Request"] = "partial/ajax"
	AUTHHEADERS["Referer"] = ref_url
	AUTHHEADERS["X-CSRF-Token"] = ''

	post_data = {
		'loginForm': 'loginForm',
		'loginForm:email': email,
		'loginForm:password': password,
		'loginForm:j_idt19': '',
		'javax.faces.ViewState': view_state,
		'javax.faces.source': 'loginForm:submit',
		'javax.faces.partial.event': 'click',
		'javax.faces.partial.execute': 'loginForm:submit loginForm',
		'javax.faces.partial.render': 'loginForm',
		'javax.faces.behavior.event': 'action',
		'javax.faces.partial.ajax': 'true'
	}
	r = s.post(auth_base + '/ap-login/jsf/login.jsf', data=post_data, headers=AUTHHEADERS)
	if r.status_code != 200:
		return ""
	ref_url = extract_redirect_url(r).replace('&amp;', '&')
	#print(ref_url)
	# redirect to link from login and extract state and code values
	r = s.get(ref_url, allow_redirects=False, headers=AUTHHEADERS)
	if r.status_code != 302:
		return ""
	ref_url2 = r.headers.get("location")
	#print(ref_url2)
	code = extract_code(ref_url2)
	state = extract_state(ref_url2)
	# load ref page
	r = s.get(ref_url2, headers=AUTHHEADERS)
	if r.status_code != 200:
		return ""

	AUTHHEADERS["Faces-Request"] = ""
	AUTHHEADERS["Referer"] = ref_url2
	post_data = {
		'_33_WAR_cored5portlet_code': code,
		'_33_WAR_cored5portlet_landingPageUrl': ''
	}
	r = s.post(base + urlsplit(ref_url2).path + '?p_auth=' + state + '&p_p_id=33_WAR_cored5portlet&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&_33_WAR_cored5portlet_javax.portlet.action=getLoginStatus', data=post_data, allow_redirects=False, headers=AUTHHEADERS)
	if r.status_code != 302:
		return ""
	ref_url3 = r.headers.get("location")
	#print(ref_url3)
	r = s.get(ref_url3, headers=AUTHHEADERS)
	#We have a new CSRF
	csrf = extract_csrf(r)
	# done!!!! we are in at last
	# Update headers for requests
	HEADERS["Referer"] = ref_url3
	HEADERS["X-CSRF-Token"] = csrf
	return ref_url3
	
def CarNetPost(s,url_base,command):
	#print(command)
	r = s.post(url_base + command, headers=HEADERS)
	return r.content
	
def CarNetPostAction(s,url_base,command,data):
	print(command)
	r = s.post(url_base + command, json=data, headers=HEADERS)
	return r.content

def retrieveCarNetInfo(s,url_base):
	print(CarNetPost(s,'https://www.volkswagen-car-net.com/portal/group/de/edit-profile/-/profile/get-vehicles-owners-verification', ''))
	print(CarNetPost(s,url_base, '/-/msgc/get-new-messages'))
	print(CarNetPost(s,url_base, '/-/vsr/request-vsr'))
	print(CarNetPost(s,url_base, '/-/vsr/get-vsr'))
	print(CarNetPost(s,url_base, '/-/cf/get-location'))
	print(CarNetPost(s,url_base, '/-/vehicle-info/get-vehicle-details'))
	print(CarNetPost(s,url_base, '/-/emanager/get-emanager'))
	print(CarNetPost(s,url_base, '/-/rah/get-request-status'))
	print(CarNetPost(s,url_base, '/-/rah/get-status'))
	print(CarNetPost(s,url_base, '/-/dimp/get-destinations'))
	print(CarNetPost(s,url_base, '/-/dimp/get-tours'))
	print(CarNetPost(s,url_base, '/-/news/get-news'))
	print(CarNetPost(s,url_base, '/-/rts/get-latest-trip-statistics'))
	print(CarNetPost(s,url_base, '/-/mainnavigation/load-car-details/WVWZZZ3HZJE506705'))
	print(CarNetPost(s,url_base, '/-/vehicle-info/get-vehicle-details'))
	print(CarNetPost(s,url_base, '/-/mainnavigation/get-preferred-dealer'))
	print(CarNetPost(s,url_base, '/-/ppoi/get-ppoi-list'))
	print(CarNetPost(s,url_base, '/-/geofence/get-fences'))
	return 0

def mqtt(s,url_base):
        MQTT.mqttc.publish(MQTT_TOPIC + '/vehicles-owners-verification', CarNetPost(s,'https://www.volkswagen-car-net.com/portal/group/de/edit-profile/-/profile/get-vehicles-owners-verification', ''), qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/new-messages', CarNetPost(s,url_base, '/-/msgc/get-new-messages') , qos=0, retain=True)
	# MQTT.mqttc.publish(MQTT_TOPIC + '/request-vsr', CarNetPost(s,url_base, '/-/vsr/request-vsr') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/vsr', CarNetPost(s,url_base, '/-/vsr/get-vsr') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/location', CarNetPost(s,url_base, '/-/cf/get-location') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/vehicle-details', CarNetPost(s,url_base, '/-/vehicle-info/get-vehicle-details') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/emanager', CarNetPost(s,url_base, '/-/emanager/get-emanager') , qos=0, retain=True)
	# MQTT.mqttc.publish(MQTT_TOPIC + '/request-status', CarNetPost(s,url_base, '/-/rah/get-request-status') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/status', CarNetPost(s,url_base, '/-/rah/get-status') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/destination', CarNetPost(s,url_base, '/-/dimp/get-destinations') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/tours', CarNetPost(s,url_base, '/-/dimp/get-tours') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/news', CarNetPost(s,url_base, '/-/news/get-news') , qos=0, retain=True)
	# MQTT.mqttc.publish(MQTT_TOPIC + '/lates-trip-statistics', CarNetPost(s,url_base, '/-/rts/get-latest-trip-statistics') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/car-details', CarNetPost(s,url_base, '/-/mainnavigation/load-car-details/WVWZZZ3HZJE506705') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/preferred-dealer', CarNetPost(s,url_base, '/-/mainnavigation/get-preferred-dealer') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/ppoi-list', CarNetPost(s,url_base, '/-/ppoi/get-ppoi-list') , qos=0, retain=True)
	MQTT.mqttc.publish(MQTT_TOPIC + '/fences', CarNetPost(s,url_base, '/-/geofence/get-fences') , qos=0, retain=True)
	return 0

def startCharge(s,url_base):
	post_data = {
		'triggerAction': True,
		'batteryPercent': '100'
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/charge-battery', post_data))
	return 0

def stopCharge(s,url_base):
	post_data = {
		'triggerAction': False,
		'batteryPercent': '99'
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/charge-battery', post_data))
	return 0

def startClimat(s,url_base):  
	post_data = {
		'triggerAction': True,
		'electricClima': True
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/trigger-climatisation', post_data))
	return 0

def stopClimat(s,url_base):
	post_data = {
		'triggerAction': False,
		'electricClima': True
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/trigger-climatisation', post_data))
	return 0

def startWindowMelt(s,url_base):
	post_data = {
		'triggerAction': True
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/trigger-windowheating', post_data))
	return 0

def stopWindowMelt(s,url_base):
	post_data = {
		'triggerAction': False
	}
	print(CarNetPostAction(s,url_base, '/-/emanager/trigger-windowheating', post_data))
	return 0

def startRemoteAccessHeating(s,url_base):
        post_data = {
		'startMode':'HEATING',
		'spin':CARNET_SPIN
        }
        print(CarNetPostAction(s,url_base, '/-/rah/quick-start', post_data))
        return 0

def startRemoteAccessVentilation(s,url_base):
        post_data = {
		'startMode':'VENTILATION',
		'spin':CARNET_SPIN
        }
        print(CarNetPostAction(s,url_base, '/-/rah/quick-start', post_data))
        return 0

def stopRemoteAccessHeating(s,url_base):
        post_data = {
        }
        print(CarNetPostAction(s,url_base, '/-/rah/quick-stop', post_data))
        return 0

def statusReqRemoteAccessHeating(s,url_base):
        print(CarNetPost(s,url_base, '/-/rah/get-request-status'))
        return 0

def statusRemoteAccessHeating(s,url_base):
        print(CarNetPost(s,url_base, '/-/rah/get-status'))
        return 0

def getVehiclesOwnersVerification(s,url_base):
        print(CarNetPost(s,'https://www.volkswagen-car-net.com/portal/group/de/edit-profile/-/profile/get-vehicles-owners-verification', ''))
        return 0

def getVehicleDetails(s,url_base):
        print(CarNetPost(s,url_base, '/-/vehicle-info/get-vehicle-details'))
        return 0
	
if __name__ == "__main__":
	s = requests.Session()
	url = CarNetLogin(s,CARNET_USERNAME,CARNET_PASSWORD)
	if url == '':
		print("Failed to login")
		sys.exit()

	# Init MQTT connections
	MQTT.init()
	#print 'MQTT initiated'
	#MQTT.mqttc.on_message = on_message
	#MQTT.mqttc.subscribe(MQTT_TOPIC_IN, qos=MQTT_QOS)

	if len(sys.argv) != 2:
		print "Need at least one argument."
		sys.exit()
	else:
		if(sys.argv[1] == "retrieveCarNetInfo"):
			retrieveCarNetInfo(s,url)
		if(sys.argv[1] == "startCharge"):
			startCharge(s,url)
		elif(sys.argv[1] == "stopCharge"):
			stopCharge(s,url)
		elif(sys.argv[1] == "startClimat"):
			startClimat(s,url)
		elif(sys.argv[1] == "stopClimat"):
			stopClimat(s,url)
		elif(sys.argv[1] == "startWindowMelt"):
			startWindowMelt(s,url)
		elif(sys.argv[1] == "stopWindowMelt"):
			stopWindowMelt(s,url)
		elif(sys.argv[1] == "startRemoteAccessHeating"):
			startRemoteAccessHeating(s,url)
		elif(sys.argv[1] == "stopRemoteAccessHeating"):
			stopRemoteAccessHeating(s,url)
                elif(sys.argv[1] == "getVehicleDetails"):
                        getVehicleDetails(s,url)
                elif(sys.argv[1] == "mqtt"):
                        mqtt(s,url)
		
		# Below is the flow the web app is using to determine when action really started
		# You should look at the notifications until it returns a status JSON like this
		# {"errorCode":"0","actionNotificationList":[{"actionState":"SUCCEEDED","actionType":"STOP","serviceType":"RBC","errorTitle":null,"errorMessage":null}]}
		#print(CarNetPost(s,url, '/-/msgc/get-new-messages'))
		#print(CarNetPost(s,url, '/-/emanager/get-notifications'))
		#print(CarNetPost(s,url, '/-/msgc/get-new-messages'))
		#print(CarNetPost(s,url, '/-/emanager/get-emanager'))
	
