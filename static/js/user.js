function save(element) {
  var token = document.getElementsByName("csrfmiddlewaretoken")[0].value
  console.log(element.nodeName);
  console.log(element.type);
  if (element.type == "checkbox") {
    var data = {
      'setting': element.id,
      'value': element.checked
    };
  } else {
    var data = {
      'setting': element.id,
      'value': element.value
    };
  }

  $.ajax({
    url: "user/save",
    method: "POST",
    headers: {"X-CSRFToken": token},
    data: JSON.stringify(data),
    success: function (result) {
      if (result.includes("Error")) {
        toastr.error(result);
      } else {
        toastr.success(result);
      }
    }
  })
}