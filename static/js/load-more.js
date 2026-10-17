const controls = document.getElementById("load-more-controls");
const grid = document.getElementById("post-grid");
const loadStatus = document.getElementById("load-more-status");
let loading = false;
controls.addEventListener("click", async (event) => {
    const button = event.target.closest(".load-more-button");
    if (!button || loading) {
        if (button) event.preventDefault();
        return;
    }
    event.preventDefault();
    loading = true;
    button.setAttribute("aria-disabled", "true");
    button.textContent = "Loading...";
    grid.setAttribute("aria-busy", "true");
    loadStatus.textContent = "";
    try {
        const url = new URL(button.href);
        url.searchParams.set("fragment", "true");
        const response = await fetch(url, { credentials: "same-origin" });
        if (!response.ok) throw new Error("Unable to load posts. Please try again.");
        const page = new DOMParser().parseFromString(await response.text(), "text/html");
        const batch = page.getElementById("post-batch");
        const nextControls = page.getElementById("load-more-controls");
        if (!batch || !nextControls) throw new Error("Unable to load posts. Please try again.");
        const count = batch.querySelectorAll(".post-card").length;
        grid.append(...batch.children);
        controls.replaceChildren(...nextControls.children);
        loadStatus.textContent = `${count} more posts loaded.${controls.children.length ? "" : " All posts are shown."}`;
        if (!controls.children.length) {
            loadStatus.tabIndex = -1;
            loadStatus.focus();
        } else {
            controls.querySelector("a").focus();
        }
    } catch (error) {
        loadStatus.textContent = error.message;
        button.textContent = "Load more";
        button.removeAttribute("aria-disabled");
    } finally {
        loading = false;
        grid.removeAttribute("aria-busy");
    }
});
