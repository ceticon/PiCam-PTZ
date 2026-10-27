"use strict";
document.querySelectorAll(".gallery-delete").forEach(button => {
    button.addEventListener("click", async () => {
        const filename = button.dataset.filename;
        if (!confirm(`Vill du radera videon ${filename}?`)) return;
        button.disabled = true;
        try {
            const response = await fetch("/api/video/delete/" + encodeURIComponent(filename), {method:"DELETE"});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Kunde inte radera");
            button.closest(".gallery-item").remove();
            const count = document.querySelectorAll("#video-grid .gallery-item").length;
            document.getElementById("video-count").textContent = count;
            document.getElementById("video-empty").hidden = count !== 0;
        } catch(error) {
            alert("Fel: " + error.message);
            button.disabled = false;
        }
    });
});
