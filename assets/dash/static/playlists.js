var current = null;

// Update the Table drag 'n drop'
function updateDragger() {
  var tables = document.getElementsByClassName('dragtable');
  for (i=0; i< tables.length; i++) {
    el = tables[i];
    var dragger = tableDragger(el, {
        dragHandler: '.handle',
        mode: 'row',
        onlyBody: true
    });
  }
}

// Disable all items
function disableAll() {
  if (current != null) {
    document.getElementById(current).style.display = "none";
    document.getElementById(current + "_name").style.display = "none";
    document.getElementById(current + "_name_label").style.display = "none";
    document.getElementById(current + "_anim_div").classList.remove("animate-750ms"); // stage animation reset
  }
  document.getElementById("new_playlist_label").style.display = "none";
  document.getElementById("new_playlist_entry").style.display = "none";
  document.getElementById("saveBtn").disabled = true;
  document.getElementById("addRecordBtn").disabled = true;
  document.getElementById("delPlaylistBtn").disabled = true;
}

// Called whenever a change is made to the current playlist
function change() {
  playlist = document.getElementById("playlists").value;
  disableAll();

  if (playlist == "Select a playlist...") {
    current = null;
    return;
  }

  document.getElementById("saveBtn").disabled = false;

  if (playlist == "Add new playlist...") {
    document.getElementById("new_playlist_label").style.display = "block";
    document.getElementById("new_playlist_entry").style.display = "block";
    current = null;
  } else {
    // Replay animation
    document.getElementById(playlist + "_anim_div").classList.add("animate-750ms");

    document.getElementById(playlist).style.display = "block";
    document.getElementById(playlist + "_name").style.display = "block";
    document.getElementById(playlist + "_name_label").style.display = "block";
    document.getElementById("addRecordBtn").disabled = false;
    document.getElementById("delPlaylistBtn").disabled = false;

    current = playlist;
  }
}

// Add a new record to the bottom of the current playlist.
function addRecord() {
  var table = document.getElementById(current).getElementsByTagName('tbody')[0];
  var row = table.insertRow();
  var length = table.rows.length;

  row.innerHTML = `<td class='handle'><i class="fas fa-bars"></i></td>\
  <td><input type="search" value="" id="${current}_${length}_title" placeholder="Enter a title..." class="namegen"></input></td>\
  <td><input type="search" value="" id="${current}_${length}_generator" placeholder="Enter the URL or search string..." class="namegen"></input></td>\
  <td><input type="search" value="" id="${current}_${length}_starttime" placeholder="Enter a start time..."></input></td>\
  <td><input type="search" value="" id="${current}_${length}_endtime" placeholder="Enter an end time..."></input></td>\
  <td><button type="button" onclick="return deleteEntry(this);" value="${playlist}_${length}"><i class="fas fa-trash-alt"></i></button></td>`

  updateDragger();
}

// Read and serialize the information from the current table.
function readTable() {
  var table = document.getElementById(current);
  output = []
  for (i=1; i<table.rows.length; i++) {
    row = table.rows[i];
    var rowdata = [];
    for (j=1; j<row.cells.length; j++) {
      cell = row.cells[j];
      rowdata.push(cell.firstChild.value);
    }
    output.push(rowdata);
  }
  return output;
}

// Do the AJAX SHUFFLE ( ﾟヮﾟ)
// (Called to communicate with Azura)
function communicate(endpoint, data, method="POST", type="application/json") {
  var xhr = new XMLHttpRequest();
  return new Promise(function (resolve, reject) {
    xhr.onreadystatechange = function () {
      // We should only run the next code if the request is complete.
      if (xhr.readyState !== 4) {
        return;
      }

      // If all good, resolve response.
      if (xhr.status == 200) {
        resolve(xhr.responseText);
      } else {
        // else, reject it.
        reject({
          status: xhr.status,
          statusText: xhr.statusText
        });
      }
    };
    xhr.open(method, endpoint);
    xhr.setRequestHeader("Content-Type", type);
    xhr.send(data);
  });
}

// Called when a playlist is saved.
function savePlaylist() {
  var endpoint = "/api/save-playlist";
  var data = {};

  var isNew = document.getElementById("playlists").value == "Add new playlist...";

  if (isNew) {
      data['id'] = document.getElementById("new_playlist_entry").value;
      data['name'] = document.getElementById("new_playlist_entry").value;
      data['entries'] = []
      data['action'] = "create";
  } else {
    data['id'] = current;
    data['name'] = document.getElementById(current + "_name").value;
    data['entries'] = readTable();
    data['action'] = "update";
  }

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
      alert(result);
      if (isNew) location.reload(true);
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
      alert("Communication failure. Nothing has been saved.");
    });
}

// Called when a playlist is deleted.
function deletePlaylist() {
  var endpoint = "/api/delete-playlist";
  var data = {'id': document.getElementById(current + "_name").value};

  var message = "Are you sure you want to delete \"" + data['id'] + "\"? This action cannot be undone..."
  if (confirm(message) == false) {
    return;
  }

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
      alert(result);
      location.reload(true);
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
      alert("Communication failure. Nothing has been changed.");
    });
}

// Called to delete an entry
function deleteEntry(element) {
  var index = element.parentNode.parentNode.rowIndex;
  document.getElementById(current).deleteRow(index);
  console.log(index);
}

// Perform on page load
document.addEventListener('DOMContentLoaded', function(event) {
  var url = new URL(window.location.href);
  var url_param = url.searchParams.get('playlist');
  var playlists = document.getElementById("playlists");

  var options = Array.apply(null, playlists.options).map(function(option) {
    return option.value;
  });

  for (var i = 0; i < 2; i++) {
    options.shift();
  }

  if (options.includes(url_param)) {
    playlists.value = url_param;
    current = url_param;
    change();
  }
});
