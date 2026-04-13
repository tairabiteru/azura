var current_id = 0;


function make_new_row(fname) {
  var $tr = $(`<tr id='row_${current_id}'></tr>`);
  $tr.append(`<td id='fname_${current_id}'>${fname}</td>`);
  $tr.append(`<td><input type='text' id='name_${current_id}'></td>`);

  var $field = $(`<div class='chip-field' id='artists_input_${current_id}'></div>`);
  $field.append("<div class='chips'></div>");
  $field.append("<input placeholder='Enter an artist...' autofocus autocomplete='off' class='chip-input'>");

  var $td = $("<td></td>");
  $td.append($field);
  $tr.append($td);

  $("#songs").append($tr);
  bind_chip(`artists_input_${current_id}`);
  current_id = current_id + 1;
}


function bind_chip(id) {
  var $input = $(`#${id}`).find(".chip-input");
  var $chips = $(`#${id}`).find(".chips");

  $(`#${id}`).bind('click',() => {
      $input.css("display", "block");
      $input.focus();
  });

    
  $input.bind('blur',()=>{
    $input.css("display", "none");
  });

  $input.bind('keypress', function(event){
    if(event.which === 13)
    {

      var $chip = $("<div></div>").addClass("chip").bind('click', handle_chip_close);
      var $chip_text = $("<span></span>").addClass("chip-text").html($input.val());
      $chip.append($chip_text)
      var $chip_button = $("<span>x</span>").addClass("chip-button");
      $chip.append($chip_button)

      $chips.append($chip);
      $input.val("");
    }
  });
}


function handle_chip_close(event){
  event.currentTarget.remove();
}


// Ensure field is empty on refresh.
$("#files").val("");

// Bind to change
$("#files").bind('change', function () {
  for (const file of this.files) {
    make_new_row(file.name);
  }
  $("#files").css("display", "none");
  $("#submit").css("display", "block");
});


var csrf = $("input[name=csrfmiddlewaretoken]").val();
$(document).on('submit', '#form', function (e) {
  e.preventDefault();
  e.stopPropagation();
});

$(document).on('click', '#submit', function () {
  $.ajaxSetup({
    headers: {'X-CSRFToken': csrf}
  });

  var data = new FormData($("#form")[0]);
  var old_files = data.getAll("files");
  data.delete("files");
  
  var rows = $("#songs").prop("rows");

  for (let i=0; i<rows.length; i++) {
    var row = rows[i];
    var id = $(row).attr("id").split("_").pop();
    var fname = $(`#fname_${id}`).html();
    var f = fname.split(".");
    var ext = f[f.length-1];
    newname = `${id}.${ext}`;
    var name = $(`#name_${id}`).val();
    var file = old_files[i];
    var artists = [];

    if (file.type != "audio/mpeg") {
      toastr.error(`Invalid file type for ${fname}: ${file.type}. Only MP3 files are accepted.`);
      return;
    }

    for (const artist of $(row).find(".chip")) {
      artists.push($(artist).find('.chip-text')[0].innerHTML);
    }

    if (!name) {
      toastr.error(`No song title has been set for ${fname}.`);
      return;
    }

    if (artists.length == 0) {
      toastr.error(`At least one artist must be specified for ${fname}.`);
      return;
    }
    
    var adata = {
      fname: newname,
      name: name,
      artists: artists
    };
    data.append(newname, JSON.stringify(adata));
    data.append(newname, file);
  }

   $("#submit").prop("disabled", true);

  $.ajax({
    type: 'POST',
    data: data,
    processData: false,
    contentType: false,
    xhr: function () {
      var xhr = new window.XMLHttpRequest();
      xhr.upload.addEventListener("progress", function(event) {
        if (event.lengthComputable) {
          var percentComplete = event.loaded / event.total;
          $("#upload_progress").val(percentComplete * 100);
        }
      }, false);

      return xhr;
    }
  });
});