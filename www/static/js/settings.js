function setLevelValue(element, value) {
  if (value > 0) {
    element.innerHTML = "+" + value;
  } else {
    element.innerHTML = value;
  }
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

function showNewEq() {
  document.getElementById("newEqOverlay").style.display = "block";
}

function hideNewEq() {
  document.getElementById("newEqOverlay").style.display = "none";
  document.getElementById("newEqName").value = "";
}

function changeEqState(state) {
  var element = document.getElementById("eq");
  var all = element.getElementsByTagName("input");
  for (i=0; i<all.length; i++) {
    all[i].disabled = !state;
  }
  document.getElementById("eq_name").disabled = !state;
}


function saveSettings() {
  var endpoint = "/api/settings/save";
  var data = {};

  var element = document.getElementById("settingsForm");
  var all = element.getElementsByTagName("input");
  for (i=0; i<all.length; i++) {
    if (all[i].type == "checkbox") {
      data[all[i].id] = all[i].checked;
    } else if (all[i].type == "number") {
      data[all[i].id] = all[i].value;
    } else {
      console.warn(all[i]);
    }
  }

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
        console.log(result);
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
}


function createEq() {
  var endpoint = "/api/eq/create";

  var newEqName = document.getElementById("newEqName").value;
  var newEqDesc = document.getElementById("newEqDesc").value;
  var newEqBase = document.getElementById("newEqBase").value;

  if (newEqName == "") {
    return alert("Error: Please enter a name for the equalizer.");
  }

  if (newEqDesc == "") {
    newEqDesc = "No description provided.";
  }

  if (newEqBase == "Select a base...") {
    newEqBase = null;
  }

  var data = {
    'name': newEqName,
    'description': newEqDesc,
    'based_on': newEqBase
  }

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
        alert(result);
        if (!result.includes("Error")) {
          window.location.reload();
        }
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
}


function changeEq() {
  var endpoint = "/api/eq/change";
  var eqName = document.getElementById("eq_name");
  var data = {'name': eqName.value};

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
        console.log(result);
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
  obtainEq(eqName.value);
}


function deleteEq() {
  var endpoint = "/api/eq/delete";
  var eqName = document.getElementById("eq_name");
  var data = {'name': eqName.value};

  if (!confirm("You are about to delete '" + eqName.value + "'. This action cannot be undone. Are you sure you want to do this?")) {
    return false;
  }

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
      alert(result);
      if (!result.includes("Error")) {
        window.location.reload();
      }
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
  obtainEq(eqName.value);
}


function obtainEq(name) {
  var endpoint = "/api/eq/obtain";
  var data = {'name': name};

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
        result = JSON.parse(result);
        if (result['response'] != "success") {
          console.warn(result);
        } else {
          for (const [band, level] of Object.entries(result['levels'])) {
            setLevelValue(document.getElementById(band + "_level"), level);
            document.getElementById(band).value = level;
          }
        }
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
}


function changeLevel(element) {
  var endpoint = "/api/eq/levelset";
  var data = {
    'name': document.getElementById("eq_name").value,
    'band': element.id,
    'level': element.value
  };
  setLevelValue(document.getElementById(element.id + "_level"), element.value);

  data = JSON.stringify(data);
  result = communicate(endpoint, data)
    .then(function (result) {
        console.log(result);
    })
    .catch(function (error) {
      console.warn("Communication failure:", error);
    });
}


// change Eq state when necessary
var useEqualizerCheckbox = document.getElementById("useEqualizer");
useEqualizerCheckbox.addEventListener('change', function() {
  changeEqState(this.checked);
})

// Perform on page load
document.addEventListener('DOMContentLoaded', function(event) {
  obtainEq(document.getElementById("eq_name").value);
  changeEqState(useEqualizerCheckbox.checked);
});
