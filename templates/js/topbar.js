// templates/topbar.js

document.addEventListener("DOMContentLoaded", () => {
  const topbar = document.getElementById("topbar");

  // Build the top bar dynamically
  topbar.innerHTML = `
    <div class="left-controls">
      <h2 id="app-title">greenchain</h2>
      <button id="back-btn" title="Go Back">←</button>
      <button id="forward-btn" title="Go Forward">→</button>
    </div>

    <div class="search-container">
      <input type="text" id="search-input" placeholder="Search...">
      <button id="search-btn">🔍</button>
    </div>

    <div class="profile-container">
      <img id="profile-pic" src="assets/profile-placeholder.png" alt="Profile Picture">
      <span id="profile-name">Guest</span>
    </div>

    <!-- Hidden profile modal -->
    <div id="profile-modal" class="modal">
      <div class="modal-content">
        <h3>Edit Profile</h3>
        <label>Name:</label>
        <input type="text" id="edit-name"><br>
        <label>Email:</label>
        <input type="email" id="edit-email"><br>
        <label>Upload Photo:</label>
        <input type="file" id="edit-photo"><br>
        <button id="save-profile">Save</button>
        <button id="close-profile">Close</button>
      </div>
    </div>
  `;

  // Navigation
  document.getElementById("back-btn").addEventListener("click", () => window.history.back());
  document.getElementById("forward-btn").addEventListener("click", () => window.history.forward());

  // Search
  document.getElementById("search-btn").addEventListener("click", () => {
    const query = document.getElementById("search-input").value.toLowerCase();
    if (!query) return alert("Please type something to search.");

    const elements = document.querySelectorAll(".kpi-card, .card");
    let found = false;

    elements.forEach(el => {
      if (el.textContent.toLowerCase().includes(query)) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.outline = "3px solid limegreen";
        setTimeout(() => (el.style.outline = ""), 2000);
        found = true;
      }
    });

    if (!found) alert("No matches found!");
  });

  // Profile handling
  const profileContainer = document.querySelector(".profile-container");
  const modal = document.getElementById("profile-modal");
  const closeBtn = document.getElementById("close-profile");
  const saveBtn = document.getElementById("save-profile");

  profileContainer.addEventListener("click", () => (modal.style.display = "flex"));
  closeBtn.addEventListener("click", () => (modal.style.display = "none"));

  saveBtn.addEventListener("click", () => {
    const name = document.getElementById("edit-name").value;
    const email = document.getElementById("edit-email").value;
    const photoInput = document.getElementById("edit-photo");

    if (name) document.getElementById("profile-name").textContent = name;

    if (photoInput.files && photoInput.files[0]) {
      const reader = new FileReader();
      reader.onload = e => (document.getElementById("profile-pic").src = e.target.result);
      reader.readAsDataURL(photoInput.files[0]);
    }

    modal.style.display = "none";
    alert(`Profile updated!\nName: ${name}\nEmail: ${email}`);
  });

  window.addEventListener("click", e => {
    if (e.target === modal) modal.style.display = "none";
  });
});

