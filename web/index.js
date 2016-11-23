var app = require('express')();
var http = require('http').Server(app);
var io = require('socket.io')(http);
var watch = require('node-watch');



app.get('/', function(req, res){
  res.sendfile('index.html');
});
app.get('/mycss.css', function(req, res){
  res.sendfile('mycss.css');
});
app.get('/myjs.js', function(req, res){
  res.sendfile('myjs.js');
});
app.get('/settings.json', function(req, res){
  res.sendfile('settings.json');
});
app.get('/alertpins.json', function(req, res){
  res.sendfile('alertpins.json');
});

io.on('connection', function(socket){
  socket.on('chat message', function(msg){
    console.log('message: ' + msg);
  });
});

io.on('connection', function(socket){
  socket.on('chat message', function(msg){
    io.emit('chat message', msg);
  });
});


http.listen(80, function(){
  console.log('listening on *:80');
});

watch('alertpins.json', function(){
	console.log('File Changed');
	io.emit('pinsChanged', "File Changed");
});