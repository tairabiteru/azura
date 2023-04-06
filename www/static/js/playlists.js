toastr.options.timeOut = 8000;

function update_dragger() {
    var tables = document.getElementsByClassName('dragtable');

    for (i=0; i<tables.length; i++) {
        var element = tables[i];
        var dragger = tableDragger(element, {
            dragHandler: '.handle',
            mode: 'row',
            onlyBody: true
        });
    }
}

function append_item(name, source, start, end) {
    var tbody = document.getElementById("playlist_items_tbody");
    var row = tbody.insertRow();

    if (tbody.rows.length > 0) {
        document.getElementById("items").style = "visibility: visible;";
    }

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
    start_input.placeholder = "Start at 00:00:00...";
    start_td.appendChild(start_input);

    var end_td = row.insertCell();
    var end_input = document.createElement('input');
    end_input.type = "search";
    end_input.value = end;
    end_input.placeholder = "End at end of track...";
    end_td.appendChild(end_input);

    var del_td = row.insertCell();
    var del_input = document.createElement('button');
    del_input.type = 'button';
    del_input.onclick = delete_item;
    var del_itag = document.createElement('i');
    del_itag.classList.add("fas");
    del_itag.classList.add("fa-trash-alt");
    del_input.appendChild(del_itag);
    del_td.appendChild(del_input);

    update_dragger();
}


function create_new_item() {
    return append_item("", "", "", "");
}


function clear_table() {
    var tbody = document.getElementById("playlist_items_tbody").innerHTML = "";
}


async function change_playlist(event) {
    if (event.value < 0) {
        clear_table();
        document.getElementById("controls").style = "visibility: visible;"
        document.getElementById("items").style = "visibility: hidden;"
        document.getElementById("playlist_name").value = "";
        document.getElementById("playlist_description").value = "";
        document.getElementById("delete_playlist_button").disabled = true;
    } else {
        document.getElementById("controls").style = "visibility: visible;"
        document.getElementById("items").style = "visibility: hidden;"
        document.getElementById("delete_playlist_button").disabled = false;
        var playlist = await get_playlist(event.value);
        populate_table(playlist);
    }
}


async function get_playlist(id) {
    data = {'playlist_id': id};
    var result = await sendXHR("/playlists/get", JSON.stringify(data));
    return JSON.parse(result);
}


function populate_table(playlist) {
    clear_table();

    document.getElementById("playlist_name").value = playlist['name'];
    document.getElementById("playlist_description").value = playlist['description'];

    var items = playlist['items'];

    for (var i=0; i<items.length; i++) {
        var item = items[i];
        append_item(item['title'], item['source'], item['start'], item['end']);        
    }
}


function delete_item(event) {
    if (event.target.tagName == "I") {
        event.target.parentNode.parentNode.parentNode.remove();
    } else {
        event.target.parentNode.parentNode.remove();
    }

    if (document.getElementById("playlist_items_tbody").rows.length == 0) {
        document.getElementById("items").style = "visibility: hidden;";
    }
}


async function delete_playlist() {
    var confirmation = confirm("Are you sure you want to delete the selected playlist? This action cannot be undone...");
    if (!confirmation) {
        return;
    }

    var playlist_id = document.getElementById("playlist_selector").value;
    var data = {'id': playlist_id};
    var response = await sendXHR("playlists/delete", JSON.stringify(data));
    response = JSON.parse(response);
    if (response['status'] == "error") {
        console.log(response);
        toastr.error(response['reason']);
        return;
    }
    alert("Playlist successfully deleted.");
    window.location.reload();
}


async function save_playlist() {
    var playlist_id = document.getElementById("playlist_selector").value;
    var playlist_name = document.getElementById("playlist_name").value;
    var playlist_description = document.getElementById("playlist_description").value;
    var items = [];

    var tbody = document.getElementById("playlist_items_tbody");

    for (var i=0; i<tbody.rows.length; i++) {
        var row = tbody.rows[i];

        if (row.cells[2].firstChild.value == "") {
            toastr.error("Error: Playlist not saved. One or more tracks are missing a source.");
            return;
        }

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
    
    var response = await sendXHR("playlists/save", JSON.stringify(data));
    response = JSON.parse(response);
    if (response['status'] == "error") {
        console.log(response);
        toastr.error(response['reason']);
        return;
    }

    if (document.getElementById("playlist_selector").value == -1) {
        alert("Playlist created. The page will now reload.");
        window.location.reload();
    }

    toastr.success("Your playlist has been saved.");
}
