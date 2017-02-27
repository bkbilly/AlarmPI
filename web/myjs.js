var socket = io();
var enabledPins = {'in': [], 'out': []}
var sensor = '<div class="sensordiv" id="sensordiv{sensorpin}">\
	<div class="sensortext" id="sensorname{sensorpin}" onclick="changeNamePin(this, {sensorpin}, \'sensor\')"></div>\
	<div class="setSensorState">\
		<div class="onoffswitch">\
			<input type="checkbox" name="onoffswitch{sensorpin}" class="onoffswitch-checkbox" \
			id="myonoffswitch{sensorpin}" onchange="changeSensorState(this, {sensorpin})">\
			<label class="onoffswitch-label" for="myonoffswitch{sensorpin}">\
				<span class="onoffswitch-inner"></span>\
				<span class="onoffswitch-switch"></span>\
			</label>\
		</div>\
	</div>\
	<div class="setSensorPin">\
		<label>Pin:</label>\
		<div id="sensorgpio{sensorpin}">55</div>\
	</div>\
</div>'
var fileref=document.createElement("link");
fileref.setAttribute("rel", "stylesheet");
fileref.setAttribute("type", "text/css");
if( /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ) {
	fileref.setAttribute("href", "mycssMobile.css");
} else {
	fileref.setAttribute("href", "mycss.css");
}
document.getElementsByTagName("head")[0].appendChild(fileref)

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

	socket.on('pinsChanged', function(msg){
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
	$.getJSON("alertpins.json").done(function(data){
		$.each(data.sensors, function(i, item){
			var tmpsensor = sensor
			tmpsensor = tmpsensor.replace(/\{sensorpin\}/g, item.pin)
			tmpsensor = tmpsensor.replace(/\{sensorname\}/g, item.name)
			$(tmpsensor).appendTo("#sensors");
		});
		refreshStatus(data);
	});
	$.getJSON("alarmStatus.json").done(function(data){
		setAlarmStatus(data);
	});
	$.getJSON("sensorsLog.json").done(function(data){
		addSensorLog(data);
	});
}

function refreshStatus(data){
	enabledPins['in'] = []
	console.log(data);
	$.each(data.sensors, function(i, alertsensor){
		enabledPins['in'].push(alertsensor.pin)
		btnColour = "";
		if (alertsensor.active === false)
			btnColour = "white";
		else
			btnColour = (alertsensor.alert === true ? "green" : "red");
		shadowBtnColour = "inset 0px 30px 40px -20px " + btnColour
		$("#sensorstatus"+alertsensor.pin).css("background-color", btnColour);
		$("#sensordiv"+alertsensor.pin).css("box-shadow", shadowBtnColour);
		$("#myonoffswitch"+alertsensor.pin).prop('checked', alertsensor.active);
		$("#sensorname"+alertsensor.pin).text(alertsensor.name);
		$("#sensorgpio"+alertsensor.pin).text(alertsensor.pin);
	});
	if(data.alarmArmed == true) {
		$("#armButton").removeClass("disarmedAlarm").addClass("armedAlarm");
	} else {
		$("#armButton").removeClass("armedAlarm").addClass("disarmedAlarm");
	}
}

function setAlarmStatus(msg){
	console.log(msg);
	hasActiveClass = $("#alertStatus").hasClass("activeAlarm")
	if (msg.alert === true && hasActiveClass === false){
		$("#alertStatus").addClass("activeAlarm");
	} else if (msg.alert === false && hasActiveClass === true){
		$("#alertStatus").removeClass("activeAlarm");
	}
}


function addSensorLog(msg){
	$.each(msg.log, function(i, tmplog){
		$("#sensorListLog").prepend("<li>"+tmplog+"</li>");
	});
}


function changeSensorState(checkbox, pin){
	console.log(checkbox);
	console.log(checkbox.checked);
	console.log(pin);
	socket.emit('setSensorState', {"pin": pin, "active": checkbox.checked});
}

var currentName;
var currentPin;
function changeNamePin(div, pin, type){
	$("#okButton").attr("onclick","saveConfigSettings('"+ type +"')");
	currentName = div.innerHTML;
	currentPin = pin;
	$("#inputName").val(currentName);
	addPinsToSelect('#inputPin', currentPin);

	if (type === 'serene'){
		$("#inputName").hide();
		$("#delSensorBTN").hide();
	} else if (type === 'newSensor') {
		$("#inputName").show();
		$("#delSensorBTN").hide();
		$("#inputName").val('');
	} else {
		$("#delSensorBTN").attr("onclick","deleteSensor('"+ pin +"')");
		$("#delSensorBTN").show();
		$("#inputName").show();
	}
	$("#myModal").show();
}

function saveConfigSettings(type){
	var newname = $("#inputName").val();
	var newpin = $("#inputPin").val();
	console.log(type);
	if (type === 'serene') {
		if (currentPin != newpin){
			socket.emit('setSerenePin', {"pin": newpin});
		}
	} else if (type === 'newSensor') {
		if (newpin !== null && newname !== ""){
			socket.emit('addSensor', {"pin": newpin, "name": newname, "active": false});
		}
	} else {
		if (currentName !== newname){
			socket.emit('setSensorName', {"pin": currentPin, "name": newname});
		}
		if (currentPin != newpin){
			socket.emit('setSensorPin', {"pin": currentPin, "newpin": newpin});
		}
	}
	closeConfigWindow();
}

function deleteSensor(pin){
	socket.emit('delSensor', {"pin": pin});
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
	for (var i = 1; i <= 27; i++) {
		disabled = ''
		selected = ''
		if ($.inArray(i, enabledPinsList) != -1 && i != selectPin)
			disabled = 'disabled'
		if (i == selectPin)
			selected = 'selected'
		$(selectDiv).append(`<option value="${i}" ${disabled} ${selected}>${i}</option>`)
	}
	// $(selectDiv).val(currentPin);
}
