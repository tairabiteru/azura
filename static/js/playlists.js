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


htmx.on("htmx:afterSettle", (event) => {
    if (event.srcElement.id == "playlist") {
        update_dragger();
    }
});


async function delete_playlist() {
    var confirmation = confirm("Are you sure you want to delete the selected playlist? This action cannot be undone...");
    if (!confirmation) {
        return;
    }

    var playlist_id = document.getElementById("playlist_selector").value;

    data = {'playlist_id': playlist_id};
    $.ajax({
        url: "/music/delete-playlist",
        method: "POST",
        headers: JSON.parse(document.getElementById("csrf_token").value),
        data: {'data': JSON.stringify(data)},
        dataType: "json",
        success: function (result) {
                alert("Playlist successfully deleted.");
                window.location.reload();
            }
    });
}


function handle_song_entry(element) {
    var list = document.getElementById("available_songs");
    var value = element.value;

    for (const opt of list.options) {
        if (opt.innerHTML == value) {
            element.id = opt.id;
            element.style.backgroundColor = "#9900ff";
            return;
        } 
    }

    element.style.backgroundColor = "#ff5555";
    element.id = "";

}


function append_entry() {
    var tr = $("<tr style='color: white;'></tr>");
    var handle = $("<td class='handle sindu_handle'><span class='material-symbols-outlined'>reorder</span></td>");
    var song = $("<td><input type='search' placeholder='Enter a song name...' list='available_songs' oninput='handle_song_entry(this);'></td>");
    var start = $("<td><input type='search' placeholder='00:00'></td>");
    var end = $("<td><input type='search placeholder='End of Track'></td>");
    var del = $("<td><button type='button' onclick='delete_entry(this);'><span class='material-symbols-outlined'>delete</span></button></td>");
    tr.append(handle, song, start, end, del);
    $("#playlist_entries_tbody").append(tr);
    update_dragger();
}


function save_playlist() {
    var playlist_id = $("#playlist_id").val();
    var name = $("#playlist_name").val();
    var description = $("#playlist_description").val();
    var data = {'playlist_id': playlist_id, 'name': name, 'description': description, 'songs': []};
    
    if (!name) {
        toastr.error("You must specify a name for the playlist.");
        return;
    }

    var tbody = document.getElementById("playlist_entries_tbody");

    for (const row of tbody.rows) {
        var cells = row.getElementsByTagName("td");
        
        var id = cells[1].firstChild.id;
        var start = cells[2].firstChild.value;
        var end = cells[3].firstChild.value;
        var song = {'id': id, 'start': start, 'end': end};

        if (!id) {
            toastr.error("One or more of the song names specified are invalid.");
            return;
        }

        data['songs'].push(song);
    }

    $.ajax({
        url: "/music/save-playlist",
        method: "POST",
        headers: JSON.parse(document.getElementById("csrf_token").value),
        data: {'data': JSON.stringify(data)},
        dataType: "json",
        success: function (result) {
                if (result['status'] == 'error') {
                    console.log(result);
                    toastr.error(result['reason']);
                    return;
                } else if (result['status'] == 'reload') {
                    alert(result['reason']);
                    window.location.reload();
                } else {
                    toastr.success("Your playlist has been saved.");
                }
            }
    });
}