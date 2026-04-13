var artists = {};
var current_id = 0;


function rm_artist(element) {
  element.parentNode.remove();
}


function add_artist(id, artist) {
  $(`#artists_${id}`).prepend(
    $(`<span class='badge badge-pill badge-primary'>${artist} <span class="close" onclick='rm_artist(this);'>&times;</span></span>`)
  );

  var artists = document.getElementById("artists");
  for (const option of artists.children) {
    if (option.innerHTML == artist) {
      return
    }
  }

  $("#artists").append(`<option>${artist}</option>`);
}


function add_row(id, fname) {
  $("#songs").append("<tr></tr>").append(
    $("<td></td>").append(`<p id='fname_${id}'>${fname}</p>`),
    $("<td></td>").append(`<input type='text' id='name_${id}'>`),
    $("<td></td>").append(`<div id='artists_${id}' class='artist-container'><input type='text' class='artists_input' id='artists_input_${id}' list='artists'></div>`)
  );

  $(`#artists_input_${id}`).on("keypress", function (e) {
    if (e.which !== 13) {
      return;
    }
    add_artist(id, this.value);
    this.value = "";
  });
}


$("#files").on("change", function () {
  for (const file of this.files) {
    add_row(current_id, file.name);
    current_id = current_id + 1;
  }
});