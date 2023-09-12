async function sendXHR(endpoint, data, method="POST", type="application/json") {
    var xhr = new XMLHttpRequest();
    return new Promise(function (resolve, reject) {
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) {
          return;
        }
  
        if (xhr.status == 200) {
          return resolve(xhr.responseText);
        } else {
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