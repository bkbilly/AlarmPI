var socket = io();
var sensor = '<div class="sensordiv" id="sensordiv{sensorpin}">\
	<div class="sensortext" id="sensorname{sensorpin}" onclick="changeSensorName(this, {sensorpin})"></div>\
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
	var span = document.getElementsByClassName("close")[0];
	span.onclick = function() {
		closeConfigWindow();
	}
	window.onclick = function(event) {
		if (event.target == modal) {
			closeConfigWindow();
		}
	}

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

	socket.on('pinsChanged', function(msg){
		refreshStatus(msg);
	});
	socket.on('alarmStatus', function(msg){
		setAlarmStatus(msg);
	});
});

function refreshStatus(data){
	console.log(data);
	$.each(data.sensors, function(i, alertsensor){
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
	if(data.settings.alarmArmed == true) {
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


function changeSensorState(checkbox, pin){
	console.log(checkbox);
	console.log(checkbox.checked);
	console.log(pin);
	socket.emit('setSensorState', {"pin": pin, "active": checkbox.checked});
}

var currentName;
var currentPin;
function changeSensorName(div, pin){
	currentName = div.innerHTML;
	currentPin = pin;
	$("#inputName").val(currentName);
	$("#inputPin").val(currentPin);
	$("#myModal").show();
}

function saveConfigSettings(){
	var newname = $("#inputName").val();
	var newpin = $("#inputPin").val();
	if (currentName !== newname){
		socket.emit('setSensorName', {"pin": currentPin, "name": newname});
	}
	if (currentPin != newpin){
		console.log("changed pin");
	}
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
}