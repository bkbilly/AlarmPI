var socket = io();
var sensor = '<div class="sensordiv" id="sensordiv{sensorpin}">\
	<div class="sphere" id="sensorstatus{sensorpin}" \
	style="height: 30px; width: 30px;background-color:{sensoractive}"></div>\
	<div class="sensortext" id="sensorname{sensorpin}"></div>\
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

$( document ).ready(function() {
	$.getJSON("alertpins.json").done(function(data){
		$.each(data.sensors, function(i, item){
			var tmpsensor = sensor
			tmpsensor = tmpsensor.replace(/\{sensorpin\}/g, item.pin)
			tmpsensor = tmpsensor.replace(/\{sensorname\}/g, item.name)
			tmpsensor = tmpsensor.replace(/\{sensoractive\}/g, "blue")
			$(tmpsensor).appendTo("#sensors");
		});
		refreshStatus(data);
	}).fail(function(jqxhr, textStatus, error){
		console.log("Python is not running...");
	});
	socket.on('pinsChanged', function(msg){
		refreshStatus(msg);
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
	if(data.settings.activateAlarm == true) {
		console.log("test");
	}
}

function changeSensorState(checkbox, pin){
	console.log(checkbox);
	console.log(checkbox.checked);
	console.log(pin);
	socket.emit('setSensorState', {"pin": pin, "active": checkbox.checked});
}