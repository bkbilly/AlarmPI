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
</div>'


$( document ).ready(function() {
	var modal = document.getElementById('sensorModal');
	var modal2 = document.getElementById('settingsModal');
	var modal3 = document.getElementById('sensorsListModal');
	window.onclick = function(event) {
		if (event.target == modal || event.target == modal2 || event.target == modal3) {
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

	socket.emit('join', {})

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

function restart(){
	$.getJSON("restart").done(function(data){
		location.reload();
	});
}

function logout(){
	$.getJSON("logout").done(function(data){
		location.reload();
	});
}

function changeUser(){
	newUser = $('#userslist').val()
	$.getJSON("switchUser?newuser=" + newUser).done(function(data){
		closeConfigWindow();
		location.reload();
	});
}

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
	refreshLogs()
	$.getJSON("getSereneSettings.json").done(function(data){
		allproperties['serenePin'] = data.pin;
	});
}

function refreshLogs(){
	loglimit = $("#loglimit").val();
	logtype = $("#logtype").val();
	$.getJSON("getSensorsLog.json?saveLimit=True&limit="+loglimit+"&type="+logtype).done(function(data){
		console.log(data)
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
			btnColour = (alertsensor.alert === true ? "red" : "green");
		if (alertsensor.online === false)
			btnColour = "blue"
		shadowBtnColour = "inset 0px 30px 40px -20px " + btnColour
		// $("#sensorstatus"+sensor).css("background-color", btnColour);
		$("#sensordiv"+sensor).css("box-shadow", shadowBtnColour);
		$("#myonoffswitch"+sensor).prop('checked', alertsensor.enabled);
		$("#sensorname"+sensor).text(alertsensor.name);
		// $("#sensorgpio"+sensor).text(sensor);
	});
	if(data.alarmArmed == true) {
		$("#armButton").removeClass("disarmedAlarm").addClass("armedAlarm");
	} else {
		$("#armButton").removeClass("armedAlarm").addClass("disarmedAlarm");
	}
	if (data.triggered === true){
		$("#alertStatus").addClass("activeAlarm");
		document.getElementById('audioalert').play()
	} else if (data.triggered === false){
		$("#alertStatus").removeClass("activeAlarm");
		document.getElementById('audioalert').pause()
		document.getElementById('audioalert').currentTime = 0
	}

}

function setAlarmStatus(data){
	allproperties['alert'] = data.alert
	console.log(data);
	hasActiveClass = $("#alertStatus").hasClass("activeAlarm")
	if (data.alert === true && hasActiveClass === false){
		$("#alertStatus").addClass("activeAlarm");
		document.getElementById('audioalert').play()
	} else if (data.alert === false && hasActiveClass === true){
		$("#alertStatus").removeClass("activeAlarm");
	}
}


function addSensorLog(msg){
	$("#systemListLog").empty();
	$.each(msg.log, function(i, tmplog){
		$("#systemListLog").prepend("<li>"+tmplog+"</li>");
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
	$("#sensorListLog").empty();
	if (type === 'newSensor') {
		var currentName = ""
		var zones = ""
		var behavior = "normal"
		$("#sensorType").show()
		$("#delSensorBTN").hide();
		$("#inputName").val('');
	} else if (type === 'oldSensor') {
		var currentName = allproperties['sensors'][sensor]['name'];
		var behavior = allproperties['sensors'][sensor]['behavior']
		var zones = allproperties['sensors'][sensor]['zones'];
		$("#sensorType").val(allproperties['sensors'][sensor]['type']).change();
		$("#sensorType").hide()
		$("#delSensorBTN").attr("onclick","deleteSensor('"+ sensor +"')");
		$("#delSensorBTN").show();
		$.getJSON("/getSensorsLog.json?limit=100&type=sensor&filterText=" + currentName).done(function(data){
			$.each(data.log, function(i, tmplog){
				$("#sensorListLog").prepend("<li>"+tmplog+"</li>");
			});
		});
	}
	
	selectSensorType($("#sensorType"));
	if (allproperties['sensors'][sensor] == undefined)
		addPinsToSelect('#GPIO-pin', '');
	else if (allproperties['sensors'][sensor]['pin'] !== undefined)
		addPinsToSelect('#GPIO-pin', allproperties['sensors'][sensor]['pin']);
	console.log(allproperties['sensors'][sensor])
	for( property in allproperties['sensors'][sensor])
		if( !['type', 'online', 'alert', 'enabled', 'name'].includes(property) ){
			sensortype = allproperties['sensors'][sensor]['type']
			$("#"+ sensortype + '-' + property).val(allproperties['sensors'][sensor][property])
		}
	$("#okButton").attr("onclick","saveConfigSettings('"+ type+"','"+sensor+"','"+currentName+"')");
	$("#inputName").val(currentName);
	$("#inputZones").val(zones);
	$("#inputBehavior").val(behavior);
	$("#sensorModal").show();
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
	var zones = $("#inputZones").val().split(/[\s,]+/);
	var sensorType = $("#sensorType").prop("value");
	var behavior = $("#inputBehavior").prop("value");
	var sensorValues = {}
	sensorValues[sensor] = {'type': sensorType, 'name': newname, 'zones': zones, 'behavior': behavior}
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
		url: "addSensor",
		dataType : 'json',
		data: JSON.stringify(sensorValues)
	});

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

function openSensorsListWindow(){
	$.getJSON("getSensorsLog.json?type=sensor&format=json&combineSensors=True&limit=0").done(function(data){
		var groups = new vis.DataSet();
		$.each(allproperties.sensors, function(i, sensor){
			console.log(sensor)
			groups.add({id: i, content: sensor.name});
		});

		var items = new vis.DataSet();
		$.each(data.log, function(i, tmplog){
			if (tmplog.timeend !== undefined ){
				items.add({
					id: i,
					content: tmplog.timediff,
					start: tmplog.time,
					end: tmplog.timeend,
					group: tmplog.type[2],
				})
			}
		});
		var options = {
			groupOrder: 'id',
			stack: false,
		};
		console.log(groups)
		console.log(items)
		var container = document.getElementById('visualization');
		var timeline = new vis.Timeline(container);
		timeline.setOptions(options);
		timeline.setGroups(groups);
		timeline.setItems(items);
	});
	document.body.style.overflowY = "hidden";
	$("#sensorsListModal").show();
}

function openConfigWindow(){
	document.body.style.overflowY = "hidden";
	$("#sensorModal").show();
}

function closeConfigWindow(){
	$("#visualization").empty();
	document.body.style.overflowY = "auto";
	$("#sensorModal").hide();
	$("#settingsModal").hide();
	$("#sensorsListModal").hide();
}

function settingsMenu(){
	$("#settingsModal").show();
	$.getJSON("getUsers").done(function(data){
		console.log(data)
		$("#userslist").empty();
		for (var index in data.allusers) {
			user = data.allusers[index]
			console.log(user)
			if (user === data.current) {
				var sensorHTML = '<option selected value ="' + user + '">' + user + '</option>'
			} else {
				var sensorHTML = '<option value ="' + user + '">' + user + '</option>'
			}
			$(sensorHTML).appendTo("#userslist");
		}

	});
	$.getJSON("getAllSettings.json").done(function(data){
		$("#settSiren-enable").prop('checked', data.serene.enable);
		addPinsToSelect('#settSiren-Pin', data.serene.pin);
		$("#settSiren-http_start").val(data.serene.http_start);
		$("#settSiren-http_stop").val(data.serene.http_stop);

		$("#settMail-enable").prop('checked', data.mail.enable);
		$("#settMail-username").val(data.mail.username);
		$("#settMail-password").val(data.mail.password);
		$("#settMail-smtpServer").val(data.mail.smtpServer);
		$("#settMail-smtpPort").val(data.mail.smtpPort);
		$("#settMail-recipients").val(data.mail.recipients);
		$("#settMail-messageSubject").val(data.mail.messageSubject);
		$("#settMail-messageBody").val(data.mail.messageBody);

		$("#settVoip-enable").prop('checked', data.voip.enable);
		$("#settVoip-username").val(data.voip.username);
		$("#settVoip-password").val(data.voip.password);
		$("#settVoip-domain").val(data.voip.domain);
		$("#settVoip-numbersToCall").val(data.voip.numbersToCall);
		$("#settVoip-timesOfRepeat").val(data.voip.timesOfRepeat);

		$("#settUI-enable").prop('checked', data.ui.https);
		$("#settUI-username").val(data.ui.username);
		$("#settUI-password").val(data.ui.password);
		$("#settUI-timezone").val(data.ui.timezone);
		$("#settUI-port").val(data.ui.port);

		$("#settMQTT-enable").prop('checked', data.mqtt.enable);
		$("#settMQTT-host").val(data.mqtt.host);
		$("#settMQTT-port").val(data.mqtt.port);
		$("#settMQTT-authentication").val(data.mqtt.authentication);
		$("#settMQTT-username").val(data.mqtt.username);
		$("#settMQTT-password").val(data.mqtt.password);
		$("#settMQTT-state_topic").val(data.mqtt.state_topic);
		$("#settMQTT-command_topic").val(data.mqtt.command_topic);
		$("#settMQTT-homeassistant").val(data.mqtt.homeassistant);

		$("#settHTTP-enable").prop('checked', data.http.enable);
		$("#settHTTP-host").val(data.http.host);
		$("#settHTTP-port").val(data.http.port);
		$("#settHTTP-https").val(data.http.https);
		$("#settHTTP-username").val(data.http.username);
		$("#settHTTP-password").val(data.http.password);
	});
	$.getJSON("getNotifiersStatus.json").done(function(data){
		for (var key in data) {
			if (data[key] === false) {
				$(".notificationstate_"+key).css("background-color", 'red');
			} else {
				$(".notificationstate_"+key).css("background-color", 'green');
			}
		};
	});

}

function saveSettings(){
	console.log("endend");
	var messageSerene = {}
	var messageMail = {}
	var messageVoip = {}
	var messageUI = {}
	var messageMQTT = {}
	var messageHTTP = {}

	var message = {
		'serene': {},
		'mail': {},
		'voip': {},
		'settings': {},
		'mqtt': {},
		'http': {},
	}

	message.serene.enable = $("#settSiren-enable").prop('checked');
	message.serene.pin = parseInt($("#settSiren-Pin").val());
	message.serene.http_start = $("#settSiren-http_start").val();
	message.serene.http_stop = $("#settSiren-http_stop").val();

	message.mail.enable = $("#settMail-enable").prop('checked');
	message.mail.username = $("#settMail-username").val();
	message.mail.password = $("#settMail-password").val();
	message.mail.smtpServer = $("#settMail-smtpServer").val();
	message.mail.smtpPort = parseInt($("#settMail-smtpPort").val());
	message.mail.recipients = $("#settMail-recipients").val().split(/[\s,]+/);
	message.mail.messageSubject = $("#settMail-messageSubject").val();
	message.mail.messageBody = $("#settMail-messageBody").val();

	message.voip.enable = $("#settVoip-enable").prop('checked');
	message.voip.username = $("#settVoip-username").val();
	message.voip.password = $("#settVoip-password").val();
	message.voip.domain = $("#settVoip-domain").val();
	message.voip.numbersToCall = $("#settVoip-numbersToCall").val().split(/[\s,]+/);
	message.voip.timesOfRepeat = $("#settVoip-timesOfRepeat").val();

	message.settings.timezone = $("#settUI-timezone").val();

	message.mqtt.enable = $("#settMQTT-enable").prop('checked');
	message.mqtt.host = $("#settMQTT-host").val();
	message.mqtt.port = parseInt($("#settMQTT-port").val());
	message.mqtt.authentication = $("#settMQTT-authentication").val() == 'true';
	message.mqtt.username = $("#settMQTT-username").val();
	message.mqtt.password = $("#settMQTT-password").val();
	message.mqtt.state_topic = $("#settMQTT-state_topic").val();
	message.mqtt.command_topic = $("#settMQTT-command_topic").val();
	message.mqtt.homeassistant = $("#settMQTT-homeassistant").val() == 'true';

	message.http.enable = $("#settHTTP-enable").prop('checked');
	message.http.host = $("#settHTTP-host").val();
	message.http.port = parseInt($("#settHTTP-port").val());
	message.http.https = $("#settHTTP-https").val() == 'true';
	message.http.username = $("#settHTTP-username").val();
	message.http.password = $("#settHTTP-password").val();

	console.log(message);
	socket.emit('setSettings', message);
	closeConfigWindow();
}


function addPinsToSelect(selectDiv, selectPin){
	try {
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
	} catch {
		console.log('not supported the addPinsToSelect')
	}
}
