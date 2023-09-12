toastr.options.timeOut = 8000;


function update_dragger() {
    var tables = document.getElementsByClassName('dragtable');

    for (i=0; i<tables.length; i++) {
        var element = tables[i];
        tableDragger(element, {
            dragHandler: '.handle',
            mode: 'row',
            onlyBody: true
        });
    }
}


function delete_entry(element) {
    if (document.getElementById("playlist_entries_tbody").rows.length == 1) {
        toastr.error("You cannot remove the last entry.");
        return;
    }
    
    if (element.tagName == "I") {
        element.parentNode.parentNode.parentNode.remove();
    } else {
        element.parentNode.parentNode.remove();
    }
}


function append_entry(name, source, start, end) {
    var tbody = document.getElementById("playlist_entries_tbody");
    var row = tbody.insertRow();

    var bars_td = row.insertCell();
    bars_td.classList.add("handle");
    var bars_itag = document.createElement('i');
    bars_itag.classList.add("fas");
    bars_itag.classList.add("fa-bars");
    bars_td.appendChild(bars_itag);

    var name_td = row.insertCell();
    var name_input = document.createElement('input');
    name_input.type = "search";
    name_input.value = name;
    name_input.placeholder = "Enter a title...";
    name_td.appendChild(name_input);

    var source_td = row.insertCell();
    var source_input = document.createElement('input');
    source_input.type = "search";
    source_input.value = source;
    source_input.placeholder = "Enter a source...";
    source_td.appendChild(source_input);

    var start_td = row.insertCell();
    var start_input = document.createElement('input');
    start_input.type = "search";
    start_input.value = start;
    start_input.placeholder = "00:00";
    start_td.appendChild(start_input);

    var end_td = row.insertCell();
    var end_input = document.createElement('input');
    end_input.type = "search";
    end_input.value = end;
    end_input.placeholder = "End of Track";
    end_td.appendChild(end_input);

    var del_td = row.insertCell();
    var del_input = document.createElement('button');
    del_input.type = 'button';
    del_input.onclick = function () {delete_entry(del_input);};
    var del_itag = document.createElement('i');
    del_itag.classList.add("fas");
    del_itag.classList.add("fa-trash-alt");
    del_input.appendChild(del_itag);
    del_td.appendChild(del_input);

    update_dragger();
}


htmx.on("htmx:afterSettle", (event) => {
    if (event.srcElement.id == "playlist") {
        update_dragger();
    }
});


async function save_playlist() {
    var playlist_id = document.getElementById("playlist_selector").value;
    var playlist_name = document.getElementById("playlist_name").value;
    var playlist_description = document.getElementById("playlist_description").value;
    var items = [];

    var tbody = document.getElementById("playlist_entries_tbody");
    var titles = [];

    for (var i=0; i<tbody.rows.length; i++) {
        var row = tbody.rows[i];

        var item = {
            'name': row.cells[1].firstChild.value,
            'source': row.cells[2].firstChild.value,
            'start': row.cells[3].firstChild.value,
            'end': row.cells[4].firstChild.value
        };

        items.push(item);
    }

    var data = {
        'id': parseInt(playlist_id),
        'name': playlist_name,
        'description': playlist_description,
        'items': items
    };

    $.ajax({
        url: "/playlists/save/",
        method: "POST",
        headers: JSON.parse(document.getElementById("csrf_token").value),
        data: JSON.stringify(data),
        dataType: "json",
        success: function (result) {
                if (result['status'] == "error") {
                    console.log(result);
                    toastr.error(result['reason']);
                    return;
                }

                if (document.getElementById("playlist_selector").value == -1) {
                    alert("Playlist created. The page will now reload.");
                    window.location.reload();
                }

                toastr.success("Your playlist has been saved.");
            }
    });
}


async function delete_playlist() {
    var confirmation = confirm("Are you sure you want to delete the selected playlist? This action cannot be undone...");
    if (!confirmation) {
        return;
    }

    var playlist_id = document.getElementById("playlist_selector").value;

    data = {'playlist_id': playlist_id};
    $.ajax({
        url: "/playlists/delete/",
        method: "POST",
        headers: JSON.parse(document.getElementById("csrf_token").value),
        data: JSON.stringify(data),
        dataType: "json",
        success: function (result) {
                alert("Playlist successfully deleted.");
                window.location.reload();
            }
    });
}