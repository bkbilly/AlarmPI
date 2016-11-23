var socket = io();
var sensor = '<div class="sensordiv">\
	<div class="sphere" id="sensorstatus{sensorpin}" \
	style="height: 30px; width: 30px;background-color:{sensoractive}"></div>\
	<div class="sensortext">\
		{sensorname}: {sensorpin}\
	</div>\
</div>'

$( document ).ready(function() {
	$.getJSON("settings.json").done(function(data){
		console.log(data)
		$.each(data.sensors, function(i, item){
			var tmpsensor = sensor
			tmpsensor = tmpsensor.replace(/\{sensorpin\}/g, item.pin)
			tmpsensor = tmpsensor.replace(/\{sensorname\}/g, item.name)
			tmpsensor = tmpsensor.replace(/\{sensoractive\}/g, "blue")
			$(tmpsensor).appendTo("#sensors");
		});
		refreshSonsorStatus();
	});
	socket.on('pinsChanged', function(msg){
		refreshSonsorStatus();
	});
});

function refreshSonsorStatus(){
	$.getJSON("alertpins.json").done(function(data){
		$.each(data.sensors, function(i, alertsensor){
			btnColour = ""
			if (alertsensor.active === false)
				btnColour = "white"
			else
				btnColour = (alertsensor.alert === true ? "green" : "red")
			$("#sensorstatus"+alertsensor.pin).css("background-color", btnColour)
		});
	}).fail(function(jqxhr, textStatus, error){
		console.log("Python is not running...");
	});
}