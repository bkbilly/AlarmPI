var socket = io();
var enabledPins = {'in': [], 'out': []}
var allproperties = {
	"sensors": [],
	"serenePin": null,
	"alarmArmed": null,
	"alert": null
}
var sensorHTMLTemplate = '<div class="sensordiv" id="sensordiv{sensor}">\
	<div class="sensortext" id="sensorname{sensor}" \
		onclick="changeSensorSettings(\'{sensor}\', \'oldSensor\')"></div>\
	<div class="setSensorState">\
		<div class="onoffswitch">\
			<input type="checkbox" name="onoffswitch{sensor}" class="onoffswitch-checkbox" \
			id="myonoffswitch{sensor}" onchange="changeSensorState(this, \'{sensor}\')">\
			<label class="onoffswitch-label" for="myonoffswitch{sensor}">\
				<span class="onoffswitch-inner"></span>\
				<span class="onoffswitch-switch"></span>\
			</label>\
		</div>\
	</div>\
	<div class="setSensorPin">\
		<label>Pin:</label>\
		<div id="sensorgpio{sensor}">55</div>\
	</div>\
</div>'
//var fileref=document.createElement("link");
//fileref.setAttribute("rel", "stylesheet");
//fileref.setAttribute("type", "text/css");
//fileref.setAttribute("href", "mycss.css");
////if( /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ) {
////} else {
////	fileref.setAttribute("href", "mycss.css");
////}
//document.getElementsByTagName("head")[0].appendChild(fileref)

$( document ).ready(function() {
	var modal = document.getElementById('myModal');
	var modal2 = document.getElementById('settingsModal');
	window.onclick = function(event) {
		if (event.target == modal || event.target == modal2) {
			closeConfigWindow();
		}
	}
	var acc = document.getElementsByClassName("accordion");
	for (i = 0; i < acc.length; i++) {
		acc[i].onclick = function() {
			this.classList.toggle("active");
			var panel = this.nextElementSibling;
			if (panel.style.maxHeight){
				panel.style.maxHeight = null;
			} else {
				panel.style.maxHeight = panel.scrollHeight + "px";
			}
		}
	}

	startAgain();

	socket.on('sensorsChanged', function(msg){
		startAgain();
	});
	socket.on('settingsChanged', function(msg){
		refreshStatus(msg);
	});
	socket.on('alarmStatus', function(msg){
		setAlarmStatus(msg);
	});
	socket.on('sensorsLog', function(msg){
		addSensorLog(msg);
	});
});

function startAgain(){
	$("#sensors").empty();
	$.getJSON("getSensors.json").done(function(data){
		$.each(data.sensors, function(sensor, item){
			var sensorHTML = sensorHTMLTemplate
			sensorHTML = sensorHTML.replace(/\{sensor\}/g, sensor)
			sensorHTML = sensorHTML.replace(/\{sensorname\}/g, item.name)
			$(sensorHTML).appendTo("#sensors");
		});
		refreshStatus(data);
	});
	$.getJSON("getAlarmStatus.json").done(function(data){
		setAlarmStatus(data);
	});
	$.getJSON("getSensorsLog.json?limit=11").done(function(data){
		addSensorLog(data);
	});
	$.getJSON("getSereneSettings.json").done(function(data){
		allproperties['serenePin'] = data.pin;
	});
}

function refreshStatus(data){
	console.log("refreshing status")
	allproperties['sensors'] = data.sensors
	allproperties['alarmArmed'] = data.alarmArmed
	enabledPins['in'] = []
	console.log(data);
	$.each(data.sensors, function(sensor, alertsensor){
		enabledPins['in'].push(sensor)
		btnColour = "";
		if (alertsensor.active === false)
			btnColour = "white";
		else
			btnColour = (alertsensor.alert === true ? "green" : "red");
		shadowBtnColour = "inset 0px 30px 40px -20px " + btnColour
		$("#sensorstatus"+sensor).css("background-color", btnColour);
		$("#sensordiv"+sensor).css("box-shadow", shadowBtnColour);
		$("#myonoffswitch"+sensor).prop('checked', alertsensor.active);
		$("#sensorname"+sensor).text(alertsensor.name);
		$("#sensorgpio"+sensor).text(sensor);
	});
	if(data.alarmArmed == true) {
		$("#armButton").removeClass("disarmedAlarm").addClass("armedAlarm");
	} else {
		$("#armButton").removeClass("armedAlarm").addClass("disarmedAlarm");
	}
}

function setAlarmStatus(data){
	allproperties['alert'] = data.alert
	console.log(data);
	hasActiveClass = $("#alertStatus").hasClass("activeAlarm")
	if (data.alert === true && hasActiveClass === false){
		$("#alertStatus").addClass("activeAlarm");
	} else if (data.alert === false && hasActiveClass === true){
		$("#alertStatus").removeClass("activeAlarm");
	}
}


function addSensorLog(msg){
	$.each(msg.log, function(i, tmplog){
		$("#sensorListLog").prepend("<li>"+tmplog+"</li>");
	});
}


function changeSensorState(checkbox, sensor){
	console.log(checkbox);
	console.log(checkbox.checked);
	console.log(sensor);
	allproperties['sensors'][sensor]['active'] = checkbox.checked
	socket.emit('setSensorState', {"sensor": sensor, "active": checkbox.checked});
}

function changeSensorSettings(sensor, type){
	if (type === 'newSensor') {
		var currentName = ""
		$("#sensorType").val('GPIO');
		$("#inputName").show();
		$("#delSensorBTN").hide();
		$("#inputName").val('');
	} else if (type === 'oldSensor') {
		var currentName = allproperties['sensors'][sensor]['name'];
		$("#sensorType").val(allproperties['sensors'][sensor]['type']).change();
		$("#delSensorBTN").attr("onclick","deleteSensor('"+ sensor +"')");
		$("#delSensorBTN").show();
		$("#inputName").show();
	}
	
	selectSensorType($("#sensorType"));
	addPinsToSelect('#inputPin', sensor);
	$("#okButton").attr("onclick","saveConfigSettings('"+ type+"','"+sensor+"','"+currentName+"')");
	$("#inputName").val(currentName);
	$("#myModal").show();
}

selectSensorType = function(Dd) {
	Dd.blur();
	if (Dd.prop("value") === "GPIO")
		$("#inputPinDiv").show();
	else
		$("#inputPinDiv").hide();
};


function saveConfigSettings(type, sensor, currentName){
	var newname = $("#inputName").val();
	var newpin = $("#inputPin").val();
	console.log(type);
	if (type === 'newSensor') {
		if (newpin !== null && newname !== ""){
			socket.emit('addSensor', {"sensor": newpin, "name": newname, "active": false});
		}
	} else if (type === 'oldSensor') {
		if (currentName !== newname){
			socket.emit('setSensorName', {"sensor": sensor, "name": newname});
		}
		if (sensor != newpin){
			socket.emit('setSensorPin', {"sensor": sensor, "newpin": newpin});
		}
	}
	closeConfigWindow();
}

function deleteSensor(sensor){
	delete sensor
	socket.emit('delSensor', {"sensor": sensor});
	closeConfigWindow();
}

function ArmDisarmAlarm(){
	if ($("#armButton").hasClass("disarmedAlarm") === true){
		socket.emit('activateAlarm');
	}
	if ($("#armButton").hasClass("armedAlarm") === true){
		socket.emit('deactivateAlarm');
	}
}

function openConfigWindow(){
	$("#myModal").show();
}

function closeConfigWindow(){
	$("#myModal").hide();
	$("#settingsModal").hide();
}

function settingsMenu(){
	$("#settingsModal").show();
	$.getJSON("getSereneSettings.json").done(function(data){
		$("#myonoffswitchSerene").prop('checked', data.enable);
		addPinsToSelect('#inputSerenePin', data.pin);
	});
	$.getJSON("getMailSettings.json").done(function(data){
		$("#myonoffswitchMail").prop('checked', data.enable);
		$("#usernameMailInput").val(data.username);
		$("#passwordMailInput").val(data.password);
		$("#smtpServerMailInput").val(data.smtpServer);
		$("#smtpPortMailInput").val(data.smtpPort);
		$("#recipientsMailInput").val(data.recipients);
		$("#messageSubjectMailInput").val(data.messageSubject);
		$("#messageBodyMailInput").val(data.messageBody);
	});
	$.getJSON("getVoipSettings.json").done(function(data){
		$("#myonoffswitchVoip").prop('checked', data.enable);
		$("#usernameVoipInput").val(data.username);
		$("#passwordVoipInput").val(data.password);
		$("#domainVoipInput").val(data.domain);
		$("#numbersToCallVoipInput").val(data.numbersToCall);
		$("#timesOfRepeatVoipInput").val(data.timesOfRepeat);
	});
	$.getJSON("getUISettings.json").done(function(data){
		$("#myonoffswitchHTTPs").prop('checked', data.https);
		$("#usernameUIInput").val(data.username);
		$("#passwordUIInput").val(data.password);
		$("#timezoneUIInput").val(data.timezone);
		$("#portUIInput").val(data.port);
	});
}

function saveSettings(){
	console.log("endend");
	var messageSerene = {}
	var messageMail = {}
	var messageVoip = {}
	var messageUI = {}

	messageSerene.enable = $("#myonoffswitchSerene").prop('checked');
	messageSerene.pin = parseInt($("#inputSerenePin").val());

	messageMail.enable = $("#myonoffswitchMail").prop('checked');
	messageMail.username = $("#usernameMailInput").val();
	messageMail.password = $("#passwordMailInput").val();
	messageMail.smtpServer = $("#smtpServerMailInput").val();
	messageMail.smtpPort = parseInt($("#smtpPortMailInput").val());
	messageMail.recipients = $("#recipientsMailInput").val().split(/[\s,]+/);
	messageMail.messageSubject = $("#messageSubjectMailInput").val();
	messageMail.messageBody = $("#messageBodyMailInput").val();

	messageVoip.enable = $("#myonoffswitchVoip").prop('checked');
	messageVoip.username = $("#usernameVoipInput").val();
	messageVoip.password = $("#passwordVoipInput").val();
	messageVoip.domain = $("#domainVoipInput").val();
	messageVoip.numbersToCall = $("#numbersToCallVoipInput").val().split(/[\s,]+/);
	messageVoip.timesOfRepeat = $("#timesOfRepeatVoipInput").val();

	messageUI.https = $("#myonoffswitchHTTPs").prop('checked');
	messageUI.username = $("#usernameUIInput").val();
	messageUI.password = $("#passwordUIInput").val();
	messageUI.timezone = $("#timezoneUIInput").val();
	messageUI.port = parseInt($("#portUIInput").val());

	console.log(messageSerene);
	console.log(messageMail);
	console.log(messageVoip);
	console.log(messageUI);
	socket.emit('setSereneSettings', messageSerene);
	socket.emit('setMailSettings', messageMail);
	socket.emit('setVoipSettings', messageVoip);
	socket.emit('setUISettings', messageUI);
	closeConfigWindow();
}


function addPinsToSelect(selectDiv, selectPin){
	$(selectDiv).empty();
	enabledPinsList = enabledPins['in'].concat(enabledPins['out'])
	enabledPinsList.push(allproperties['serenePin'].toString())
	for (var i = 1; i <= 27; i++) {
		disabled = ''
		selected = ''
		if ($.inArray(i.toString(), enabledPinsList) != -1 && i != selectPin)
			disabled = 'disabled'
		if (i == selectPin)
			selected = 'selected'
		$(selectDiv).append(`<option value="${i}" ${disabled} ${selected}>${i}</option>`)
	}
}
