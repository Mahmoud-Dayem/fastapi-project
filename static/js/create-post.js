const postModal = document.getElementById("post-modal");
document.getElementById("open-post-modal").addEventListener("click", () => {
    postModal.showModal();
});
document.getElementById("close-post-modal").addEventListener("click", () => {
    postModal.close();
});

const createPostForm = document.getElementById("create-post-form");
if (createPostForm) {
    createPostForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = createPostForm.querySelector('[type="submit"]');
        const errorMessage = document.getElementById("create-post-error");
        errorMessage.hidden = true;
        submitButton.disabled = true;
        submitButton.textContent = "Publishing…";
        try {
            const response = await fetch(createPostForm.action, {
                method: "POST",
                body: new FormData(createPostForm),
                credentials: "same-origin",
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || "Unable to create the post.");
            }
            window.location.assign(result.url);
        } catch (error) {
            errorMessage.textContent = error.message || "Unable to create the post. Please try again.";
            errorMessage.hidden = false;
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Publish post";
        }
    });
}
