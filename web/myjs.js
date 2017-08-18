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
	<!-- <div class="setSensorPin">\
		<label>Pin:</label>\
		<div id="sensorgpio{sensor}">55</div>\
	</div> -->\
</div>'


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
			this.classList.toggle("enabled");
			var panel = this.nextElementSibling;
			if (panel.style.maxHeight){
				panel.style.maxHeight = null;
			} else {
				panel.style.maxHeight = panel.scrollHeight + "px";
			}
		}
	}

	startAgain();

	$('#logtype').change(function() {
		refreshLogs();
	});
	$('#loglimit').change(function() {
		refreshLogs();
	});


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
	$.getJSON("getSereneSettings.json").done(function(data){
		allproperties['serenePin'] = data.pin;
	});
	refreshLogs()
}

function refreshLogs(){
	$("#sensorListLog").empty();
	loglimit = $("#loglimit").val();
	logtype = $("#logtype").val();
	$.getJSON("getSensorsLog.json?limit="+loglimit+"&type="+logtype).done(function(data){
		addSensorLog(data);
	});
}
function refreshStatus(data){
	console.log("refreshing status")
	allproperties['sensors'] = data.sensors
	allproperties['alarmArmed'] = data.alarmArmed
	enabledPins['in'] = []
	console.log(data);
	$.each(data.sensors, function(sensor, alertsensor){
		enabledPins['in'].push(alertsensor.pin)
		btnColour = "";
		if (alertsensor.enabled === false)
			btnColour = "white";
		else
			btnColour = (alertsensor.alert === true ? "green" : "red");
		if (alertsensor.online === false)
			btnColour = "blue"
		shadowBtnColour = "inset 0px 30px 40px -20px " + btnColour
		$("#sensorstatus"+sensor).css("background-color", btnColour);
		$("#sensordiv"+sensor).css("box-shadow", shadowBtnColour);
		$("#myonoffswitch"+sensor).prop('checked', alertsensor.enabled);
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
	allproperties['sensors'][sensor]['enabled'] = checkbox.checked
	socket.emit('setSensorState', {"sensor": sensor, "enabled": checkbox.checked});
}

function changeSensorSettings(sensor, type){
	if (type === 'newSensor') {
		var currentName = ""
		$("#sensorType").show()
		$("#delSensorBTN").hide();
		$("#inputName").val('');
	} else if (type === 'oldSensor') {
		var currentName = allproperties['sensors'][sensor]['name'];
		$("#sensorType").val(allproperties['sensors'][sensor]['type']).change();
		$("#sensorType").hide()
		$("#delSensorBTN").attr("onclick","deleteSensor('"+ sensor +"')");
		$("#delSensorBTN").show();
	}
	
	selectSensorType($("#sensorType"));
	if (allproperties['sensors'][sensor] == undefined)
		addPinsToSelect('#GPIO-pin', '');
	else
		addPinsToSelect('#GPIO-pin', allproperties['sensors'][sensor]['pin']);
	console.log(allproperties['sensors'][sensor])
	$("#okButton").attr("onclick","saveConfigSettings('"+ type+"','"+sensor+"','"+currentName+"')");
	$("#inputName").val(currentName);
	$("#myModal").show();
}

selectSensorType = function(Dd) {
	sensorType = Dd.prop("value")
	$('[id^="inputDiv"]').each(function(){
		$(this).hide();
	});
	$('[id^="inputDiv'+sensorType+'"]').each(function(){
		$(this).show();
	});
};

function saveConfigSettings(type, sensor, currentName){
	var newname = $("#inputName").val();
	var sensorType = $("#sensorType").prop("value");
	var sensorValues = {}
	sensorValues[sensor] = {'type': sensorType, 'name': newname}
	$('#inputDiv'+sensorType+' [id^="'+sensorType+'-"]').each(function(){
		var key = this.id.replace(sensorType+'-', '');
		var value = $(this).val();
		console.log(key, value);
		sensorValues[sensor][key] = value;
	});
	console.log(JSON.stringify(sensorValues))
	$.ajax({
		type: 'POST',
		contentType: 'application/json',
		url: "addSensor2",
		dataType : 'json',
		data: JSON.stringify(sensorValues)
	});

	// socket.emit('addSensor', sensorValues);
	// var newname = $("#inputName").val();
	// var newpin = $("#GPIO-pin").val();
	// console.log(type);
	// if (type === 'newSensor') {
	// 	if (newpin !== null && newname !== ""){
	// 		socket.emit('addSensor', {"sensor": newpin, "name": newname, "enabled": false});
	// 	}
	// } else if (type === 'oldSensor') {
	// 	if (currentName !== newname){
	// 		socket.emit('setSensorName', {"sensor": sensor, "name": newname});
	// 	}
	// 	if (sensor != newpin){
	// 		socket.emit('setSensorPin', {"sensor": sensor, "newpin": newpin});
	// 	}
	// }
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
	document.body.style.overflowY = "hidden";
	$("#myModal").show();
}

function closeConfigWindow(){
	document.body.style.overflowY = "auto";
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
		$("#settMail-enable").prop('checked', data.enable);
		$("#settMail-username").val(data.username);
		$("#settMail-password").val(data.password);
		$("#settMail-smtpServer").val(data.smtpServer);
		$("#settMail-smtpPort").val(data.smtpPort);
		$("#settMail-recipients").val(data.recipients);
		$("#settMail-messageSubject").val(data.messageSubject);
		$("#settMail-messageBody").val(data.messageBody);
	});
	$.getJSON("getVoipSettings.json").done(function(data){
		$("#settVoip-enable").prop('checked', data.enable);
		$("#settVoip-username").val(data.username);
		$("#settVoip-password").val(data.password);
		$("#settVoip-domain").val(data.domain);
		$("#settVoip-numbersToCall").val(data.numbersToCall);
		$("#settVoip-timesOfRepeat").val(data.timesOfRepeat);
	});
	$.getJSON("getUISettings.json").done(function(data){
		$("#settUI-enable").prop('checked', data.https);
		$("#settUI-username").val(data.username);
		$("#settUI-password").val(data.password);
		$("#settUI-timezone").val(data.timezone);
		$("#settUI-port").val(data.port);
	});
	$.getJSON("getMQTTSettings.json").done(function(data){
		$("#settMQTT-enable").prop('checked', data.enable);
		$("#settMQTT-host").val(data.host);
		$("#settMQTT-port").val(data.port);
		$("#settMQTT-authentication").val(data.authentication);
		$("#settMQTT-username").val(data.username);
		$("#settMQTT-password").val(data.password);
		$("#settMQTT-state_topic").val(data.state_topic);
		$("#settMQTT-command_topic").val(data.command_topic);
	});
}

function saveSettings(){
	console.log("endend");
	var messageSerene = {}
	var messageMail = {}
	var messageVoip = {}
	var messageUI = {}
	var messageMQTT = {}

	messageSerene.enable = $("#myonoffswitchSerene").prop('checked');
	messageSerene.pin = parseInt($("#inputSerenePin").val());

	messageMail.enable = $("#settMail-enable").prop('checked');
	messageMail.username = $("#settMail-username").val();
	messageMail.password = $("#settMail-password").val();
	messageMail.smtpServer = $("#settMail-smtpServer").val();
	messageMail.smtpPort = parseInt($("#settMail-smtpPort").val());
	messageMail.recipients = $("#settMail-recipients").val().split(/[\s,]+/);
	messageMail.messageSubject = $("#settMail-messageSubject").val();
	messageMail.messageBody = $("#settMail-messageBody").val();

	messageVoip.enable = $("#settVoip-enable").prop('checked');
	messageVoip.username = $("#settVoip-username").val();
	messageVoip.password = $("#settVoip-password").val();
	messageVoip.domain = $("#settVoip-domain").val();
	messageVoip.numbersToCall = $("#settVoip-numbersToCall").val().split(/[\s,]+/);
	messageVoip.timesOfRepeat = $("#settVoip-timesOfRepeat").val();

	messageUI.https = $("#settUI-enable").prop('checked');
	messageUI.username = $("#settUI-username").val();
	messageUI.password = $("#settUI-password").val();
	messageUI.timezone = $("#settUI-timezone").val();
	messageUI.port = parseInt($("#settUI-port").val());

	messageMQTT.enable = $("#settMQTT-enable").prop('checked');
	messageMQTT.host = $("#settMQTT-host").val();
	messageMQTT.port = parseInt($("#settMQTT-port").val());
	messageMQTT.authentication = $("#settMQTT-authentication").val() == 'true';
	messageMQTT.username = $("#settMQTT-username").val();
	messageMQTT.password = $("#settMQTT-password").val();
	messageMQTT.state_topic = $("#settMQTT-state_topic").val();
	messageMQTT.command_topic = $("#settMQTT-command_topic").val();

	console.log(messageSerene);
	console.log(messageMail);
	console.log(messageVoip);
	console.log(messageUI);
	console.log(messageMQTT);
	socket.emit('setSereneSettings', messageSerene);
	socket.emit('setMailSettings', messageMail);
	socket.emit('setVoipSettings', messageVoip);
	socket.emit('setUISettings', messageUI);
	socket.emit('setMQTTSettings', messageMQTT);
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
