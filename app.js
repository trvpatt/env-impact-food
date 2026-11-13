const screens = {
  landing: document.querySelector("#landing-screen"),
  auth: document.querySelector("#auth-screen"),
  survey: document.querySelector("#survey-screen"),
  app: document.querySelector("#app-shell")
};

const pages = {
  home: { element: document.querySelector("#home-page"), title: "Home" },
  report: { element: document.querySelector("#report-page"), title: "Impact report" },
  restaurants: { element: document.querySelector("#restaurants-page"), title: "Restaurants" },
  recipes: { element: document.querySelector("#recipes-page"), title: "Recipes" },
  farms: { element: document.querySelector("#farms-page"), title: "Find local food" },
  community: { element: document.querySelector("#community-page"), title: "Get involved" },
  profile: { element: document.querySelector("#profile-page"), title: "My profile" }
};

const previewPanel = document.querySelector("#preview-panel");
const previewContent = document.querySelector("#preview-content");
const recipeModal = document.querySelector("#recipe-modal");
const recipeModalContent = document.querySelector("#recipe-modal-content");
const recipesStatus = document.querySelector("#recipes-status");
const restaurantsStatus = document.querySelector("#places-status");
const recipeResults = document.querySelector("#recipe-results");
const restaurantResults = document.querySelector("#restaurant-results");
let selectedDiet = "vegetarian";
let selectedCuisine = "Thai";
let selectedRestaurantDiet = "vegetarian";
let selectedRestaurantView = "map";
let selectedCostDiet = "vegetarian";
let selectedRange = "week";
let toastTimeout;
let returnToAppAfterSurvey = false;
let activePage = "home";
let lastRecipeTrigger = null;
let activeRecipe = null;
let surveyCuisines = [];
let selectedSurveyDiet = "vegetarian";
let surveyStepIndex = 0;
let favoriteRecipes = [];
let favoriteRestaurants = [];
let restaurantPlaces = [];
let lastRestaurantLocation = "";
const directorySearches = {};
let demoProfile = { firstName: "", lastName: "", email: "", birthday: "", address: "" };

function readFavorites(key) {
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "[]");
    if (!Array.isArray(saved)) throw new TypeError("Favorite data is not a list.");
    return saved.filter((item) => item && typeof item === "object");
  } catch (error) {
    console.error(`Could not read ${key} from browser storage.`, error);
    showToast("Saved favorites could not be read from this browser.");
    return [];
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function updateProfileDisplay() {
  const fullName = [demoProfile.firstName, demoProfile.lastName].filter(Boolean).join(" ") || "Demo member";
  const initial = fullName.charAt(0).toUpperCase();
  document.querySelector(".profile-button .avatar").textContent = initial;
  document.querySelector("#profile-name").textContent = fullName === "Demo member" ? "Your journey" : `${fullName}’s journey`;
  document.querySelector("#profile-title").textContent = fullName;
  document.querySelector("#profile-avatar-large").textContent = initial;
  document.querySelector("#profile-email").textContent = demoProfile.email || "Not connected in preview";
  document.querySelector("#profile-address").textContent = demoProfile.address || "Not provided";
  const age = demoProfile.birthday
    ? (() => {
      const birthday = new Date(`${demoProfile.birthday}T00:00:00`);
      const now = new Date();
      let years = now.getFullYear() - birthday.getFullYear();
      if (now < new Date(now.getFullYear(), birthday.getMonth(), birthday.getDate())) years -= 1;
      return years;
    })()
    : null;
  document.querySelector("#profile-age").textContent = age !== null && Number.isFinite(age) ? `${age} (preview only)` : "Not provided";
}

function showScreen(name) {
  Object.entries(screens).forEach(([key, screen]) => {
    screen.hidden = key !== name;
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showAuth(signUp = false) {
  showScreen("auth");
  setAuthMode(signUp);
  document.querySelector("#auth-email").focus();
}

function showSurvey(fromApp = false) {
  returnToAppAfterSurvey = fromApp;
  surveyStepIndex = 0;
  renderSurveyStep();
  showScreen("survey");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function enterApp(page = "home") {
  showScreen("app");
  setPage(page);
}

function setPage(name) {
  if (!pages[name]) return;
  activePage = name;
  Object.entries(pages).forEach(([key, page]) => {
    const active = key === name;
    page.element.hidden = !active;
    page.element.classList.toggle("active", active);
  });
  document.querySelectorAll(".nav-link").forEach((button) => {
    const active = button.dataset.page === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.querySelector("#page-breadcrumb").textContent = pages[name].title;
  closePreview();
  if (name === "profile") renderFavoriteLists();
  if (name === "farms" && demoProfile.address && !document.querySelector("#farm-area").value) {
    document.querySelector("#farm-area").value = demoProfile.address;
  }
  if (name === "restaurants" && demoProfile.address && !document.querySelector("#area-search-input").value) {
    document.querySelector("#area-search-input").value = demoProfile.address;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(toastTimeout);
  toastTimeout = window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function setAuthMode(signUp) {
  document.querySelector("#signup-fields").hidden = !signUp;
  document.querySelector("#signup-password-fields").hidden = !signUp;
  document.querySelector("#auth-title").textContent = signUp ? "Let’s get started." : "Welcome back.";
  document.querySelector(".auth-subtitle").textContent = signUp
    ? "A few details for your demo account preview."
    : "A little more plant-powered, one choice at a time.";
  document.querySelector("#auth-submit").innerHTML = `${signUp ? "Create account" : "Sign in"} <span aria-hidden="true">→</span>`;
  document.querySelector("#toggle-auth-mode").textContent = signUp ? "I already have an account" : "I need to sign up";
  document.querySelector("#forgot-password").hidden = signUp;
  document.querySelector("#auth-message").textContent = "";
  document.querySelectorAll("#auth-form .invalid").forEach((field) => field.classList.remove("invalid"));
  const password = document.querySelector('[name="password"]');
  password.autocomplete = signUp ? "new-password" : "current-password";
}

function clearInvalidFields() {
  document.querySelectorAll("#auth-form .invalid").forEach((field) => field.classList.remove("invalid"));
}

function validateSignUp(form) {
  const errors = [];
  const requiredNames = ["firstName", "lastName", "birthday", "email", "password", "confirmPassword"];
  requiredNames.forEach((name) => {
    const input = form.elements.namedItem(name);
    if (!input.value.trim()) {
      input.closest("label").classList.add("invalid");
      errors.push(input.labels[0]?.textContent.trim() || "Required field");
    }
  });
  const email = form.elements.namedItem("email");
  if (email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    email.closest("label").classList.add("invalid");
    errors.push("Enter a valid email address");
  }
  const birthday = form.elements.namedItem("birthday");
  if (birthday.value) {
    const birthDate = new Date(`${birthday.value}T00:00:00`);
    const adultDate = new Date();
    adultDate.setFullYear(adultDate.getFullYear() - 18);
    if (Number.isNaN(birthDate.getTime()) || birthDate > adultDate) {
      birthday.closest("label").classList.add("invalid");
      errors.push("You must be at least 18");
    }
  }
  const password = form.elements.namedItem("password");
  if (password.value && !/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(password.value)) {
    password.closest("label").classList.add("invalid");
    errors.push("Password needs 8+ characters, upper- and lowercase letters, and a number");
  }
  const confirm = form.elements.namedItem("confirmPassword");
  if (confirm.value && password.value !== confirm.value) {
    confirm.closest("label").classList.add("invalid");
    errors.push("Passwords do not match");
  }
  return errors;
}

function handleAuthSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  clearInvalidFields();
  const signUp = !document.querySelector("#signup-fields").hidden;
  if (signUp) {
    const errors = validateSignUp(form);
    if (errors.length) {
      document.querySelector("#auth-message").textContent = `Please correct invalid fields: ${errors.join("; ")}.`;
      return;
    }
  } else {
    const email = form.elements.namedItem("email");
    const password = form.elements.namedItem("password");
    if (!email.value.trim() || !password.value) {
      if (!email.value.trim()) email.closest("label").classList.add("invalid");
      if (!password.value) password.closest("label").classList.add("invalid");
      document.querySelector("#auth-message").textContent = "Enter an email address and password to preview the sign-in form.";
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
      email.closest("label").classList.add("invalid");
      document.querySelector("#auth-message").textContent = "Enter a valid email address.";
      return;
    }
  }
  if (signUp) {
    demoProfile = {
      firstName: form.elements.namedItem("firstName").value.trim(),
      lastName: form.elements.namedItem("lastName").value.trim(),
      email: form.elements.namedItem("email").value.trim(),
      birthday: form.elements.namedItem("birthday").value,
      address: form.elements.namedItem("address").value.trim()
    };
    updateProfileDisplay();
  }
  document.querySelector("#auth-message").textContent =
    "Account services aren’t connected. No information was sent or saved. Choose “Continue with the demo” to explore.";
}

function sourcePreview() {
  document.querySelector("#preview-heading").textContent = "SOURCES & APPROACH";
  previewContent.innerHTML = `
    <p class="preview-kicker">OUR SOURCES &amp; APPROACH</p>
    <h2>Grounded information, without the overclaiming.</h2>
    <p>Environmental figures are global food-production averages from Poore &amp; Nemecek (2018), published by Our World in Data. They provide context, not a personal prediction.</p>
    <div class="preview-meta"><span>Global averages</span><span>Per kilogram</span></div>
    <hr class="preview-divider">
    <p>The food-cost comparison comes from a 2021 modelling study covering 150 countries. It used 2017 prices and estimated health-care and climate costs; results vary by region and dietary pattern.</p>
    <p>All profile, impact-report, and weekly meal details in this preview are examples. They are not generated from real user data.</p>
    <div class="preview-actions"><a class="button button-green" href="https://ourworldindata.org/environmental-impacts-of-food" target="_blank" rel="noopener noreferrer">Read the source ↗</a><a class="button button-outline" href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8581186/" target="_blank" rel="noopener noreferrer">Diet cost study ↗</a></div>
  `;
  openPreview();
}

function openPreview() {
  previewPanel.classList.add("open");
  previewPanel.setAttribute("aria-hidden", "false");
  document.body.classList.add("preview-open");
  document.querySelector("#close-preview").focus();
}

function closePreview() {
  previewPanel.classList.remove("open");
  previewPanel.setAttribute("aria-hidden", "true");
  document.body.classList.remove("preview-open");
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function openRestaurant(place) {
  const mapsUrl = safeExternalUrl(place.googleMapsUri);
  const websiteUrl = safeExternalUrl(place.websiteUri);
  const name = place.name || "Restaurant";
  const rating = place.rating ? `${Number(place.rating).toFixed(1)} ★${place.userRatingCount ? ` · ${Number(place.userRatingCount).toLocaleString()} reviews` : ""}` : null;
  document.querySelector("#preview-heading").textContent = "PLACE DETAILS";
  previewContent.innerHTML = `
    <p class="preview-kicker">NEARBY PLACE · GOOGLE MAPS</p>
    <h2>${escapeHtml(name)}</h2>
    <div class="preview-meta"><span>${escapeHtml(selectedRestaurantDiet)} search match</span>${rating ? `<span>${escapeHtml(rating)}</span>` : ""}</div>
    <p>${place.address ? escapeHtml(place.address) : "Address not listed."}</p>
    <p>Search results aren’t verified dietary offerings. Check the restaurant’s menu for current options.</p>
    <div class="preview-actions">
      ${mapsUrl ? `<a class="button button-green" href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener noreferrer">View in Google Maps ↗</a>` : ""}
      ${websiteUrl ? `<a class="button button-outline" href="${escapeHtml(websiteUrl)}" target="_blank" rel="noopener noreferrer">Restaurant website ↗</a>` : ""}
    </div>
    <hr class="preview-divider"><p class="frame-note">Place information provided by Google Maps Platform.</p>`;
  openPreview();
}

const meatTerms = /\b(beef|pork|ham|bacon|lamb|mutton|chicken|turkey|duck|fish|salmon|tuna|shrimps?|prawns?|crabs?|lobsters?|anchov(?:y|ies)|chorizo|sausages?|salami|prosciutto|pepperoni|pancetta|frankfurters?|hot dogs?|squid|calamari|mussels?|clams?|scallops?|oysters?|gelatin|gelatine|lard|suet|oyster sauce|fish sauce|worcestershire)\b/i;
const animalProductTerms = /\b(milk|cream|butter|cheese|yogurt|yoghurt|ghee|egg|honey|whey|casein|mayonnaise|mayonaise|gelatin|gelatine|dairy|parmesan|ricotta|mozzarella|paneer)\b/i;
const plantMilkTerms = /\b(almond|coconut|oat|soy|soya|rice|cashew|hemp|pea|hazelnut) milk\b/i;

function ingredientNames(meal) {
  const ingredients = [];
  for (let index = 1; index <= 20; index += 1) {
    const name = meal[`strIngredient${index}`]?.trim();
    if (name) ingredients.push(name.toLowerCase());
  }
  return ingredients;
}

function fitsDiet(meal, diet) {
  if (diet === "mediterranean") return true;
  const ingredients = ingredientNames(meal);
  const listed = [meal.strMeal || "", ...ingredients].join(" ");
  if (!ingredients.length || meatTerms.test(listed)) return false;
  return diet !== "vegan" || !ingredients.some((ingredient) =>
    animalProductTerms.test(ingredient) && !plantMilkTerms.test(ingredient)
  );
}

async function fetchMealDetails(meals) {
  const ids = [...new Set(meals.map((meal) => meal.idMeal).filter(Boolean))].slice(0, 40);
  const responses = await Promise.all(ids.map(async (id) => {
    const response = await fetch(`https://www.themealdb.com/api/json/v1/1/lookup.php?i=${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error("Recipe details could not be loaded.");
    const data = await response.json();
    return data.meals?.[0] || null;
  }));
  return responses.filter(Boolean);
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function toRecipe(meal, extra = {}) {
  const ingredients = ingredientNames(meal).map((name, index) => {
    const measure = meal[`strMeasure${index + 1}`]?.trim();
    return `${measure ? `${measure} ` : ""}${name}`;
  });
  return {
    idMeal: meal.idMeal,
    name: meal.strMeal,
    image: meal.strMealThumb,
    url: meal.strSource || `https://www.themealdb.com/meal/${meal.idMeal}`,
    area: meal.strArea || selectedCuisine,
    ingredients,
    instructions: meal.strInstructions || "",
    ...extra
  };
}

function openRecipePreview(recipe, trigger) {
  activeRecipe = recipe;
  lastRecipeTrigger = trigger;
  const image = safeExternalUrl(recipe.image);
  const url = safeExternalUrl(recipe.url);
  recipeModalContent.innerHTML = `
    ${image ? `<img class="recipe-modal-image" src="${escapeHtml(image)}" alt="">` : ""}
    <p class="preview-kicker">${escapeHtml(recipe.diet || `${selectedDiet} idea`)} · ${escapeHtml(recipe.area || "Plant-forward")}</p>
    <h2 id="recipe-modal-title">${escapeHtml(recipe.name || "A good thing to cook")}</h2>
    ${recipe.matchCount ? `<p class="recipe-match-note">Matches ${recipe.matchCount} of your ingredients${recipe.matchedIngredients?.length ? `: ${escapeHtml(recipe.matchedIngredients.join(", "))}` : ""}.</p>` : ""}
    ${recipe.instructions ? `<p class="recipe-instructions">${escapeHtml(recipe.instructions.slice(0, 950))}${recipe.instructions.length > 950 ? "…" : ""}</p>` : ""}
    ${recipe.ingredients?.length ? `<h3>Ingredients</h3><ul class="recipe-ingredient-list">${recipe.ingredients.slice(0, 16).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    <p class="recipe-disclaimer">Recipe details come from the linked source. Check the full recipe for dietary needs and ingredient substitutions.</p>
    ${url ? `<a class="button button-green button-full" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original recipe ↗</a>` : ""}`;
  updateRecipeFavoriteButton();
  recipeModal.hidden = false;
  document.body.classList.add("recipe-modal-open");
  document.querySelector(".recipe-modal-close").focus();
}

function closeRecipePreview() {
  if (recipeModal.hidden) return;
  recipeModal.hidden = true;
  document.body.classList.remove("recipe-modal-open");
  activeRecipe = null;
  lastRecipeTrigger?.focus();
}

function renderRecipes(recipes, options = {}) {
  recipeResults.replaceChildren();
  if (!recipes.length) {
    setStatus(recipesStatus, options.emptyMessage || "No recipes matched those filters. Try another cuisine or different ingredients.", true);
    return;
  }
  setStatus(recipesStatus, `${recipes.length} recipe${recipes.length === 1 ? "" : "s"} found. Select a card for details and the original source.`);
  recipes.forEach((recipe) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "recipe-card";
    card.setAttribute("aria-label", `Preview recipe: ${recipe.name}`);
    const image = safeExternalUrl(recipe.image);
    card.innerHTML = `
      ${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : `<div class="recipe-card-image-placeholder">✳</div>`}
      <span class="recipe-card-body">
        <strong class="recipe-card-title">${escapeHtml(recipe.name)}</strong>
        <span class="recipe-card-footer"><span>${escapeHtml(recipe.area || "Plant-forward")}</span><span>${recipe.matchCount ? `${recipe.matchCount} match${recipe.matchCount === 1 ? "" : "es"}` : "View recipe"} ↗</span></span>
      </span>`;
    card.addEventListener("click", () => openRecipePreview(recipe, card));
    recipeResults.append(card);
  });
}

async function browseCuisine() {
  const button = document.querySelector("#browse-recipes-button");
  if (selectedCuisine === "Favorites") {
    document.querySelector("#recipes-results-title").textContent = "Your favorite recipes";
    if (!favoriteRecipes.length) {
      renderRecipes([], { emptyMessage: "Please favorite some recipes first prior to selecting this filter!" });
      return;
    }
    renderRecipes(favoriteRecipes);
    return;
  }
  button.disabled = true;
  button.innerHTML = "Finding recipes <span aria-hidden=\"true\">…</span>";
  recipeResults.replaceChildren();
  document.querySelector("#recipes-results-title").textContent = `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} ${selectedCuisine} ideas`;
  setStatus(recipesStatus, `Searching ${selectedCuisine} recipes and checking listed ingredients…`);
  try {
    const response = await fetch(`https://www.themealdb.com/api/json/v1/1/filter.php?a=${encodeURIComponent(selectedCuisine)}`);
    if (!response.ok) throw new Error("The recipe service could not be reached. Please try again.");
    const data = await response.json();
    if (!data.meals?.length) {
      renderRecipes([], { emptyMessage: `No ${selectedCuisine} recipes were returned. Try another cuisine.` });
      return;
    }
    const details = await fetchMealDetails(data.meals);
    const compatible = details.filter((meal) => fitsDiet(meal, selectedDiet)).slice(0, 24);
    renderRecipes(compatible.map((meal) => toRecipe(meal, {
      area: meal.strArea || selectedCuisine,
      diet: `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} search match`
    })));
  } catch (error) {
    setStatus(recipesStatus, `${error.message || "Recipes could not be loaded."} Check your connection and try again.`, true);
  } finally {
    button.disabled = false;
    button.innerHTML = "Find recipes <span aria-hidden=\"true\">→</span>";
  }
}

function normalizeIngredient(value) {
  return value.trim().toLowerCase().replace(/[^a-z0-9 -]/g, "").replace(/\s+/g, " ");
}

async function findRecipesByIngredients(event) {
  event.preventDefault();
  const input = document.querySelector("#ingredients-input");
  const rawIngredients = input.value.trim();
  if (!rawIngredients.includes(",")) {
    setStatus(recipesStatus, "Please follow the formatting instructions!", true);
    input.focus();
    return;
  }
  const ingredients = [...new Set(rawIngredients.split(",").map(normalizeIngredient).filter(Boolean))].slice(0, 5);
  if (ingredients.length < 2) {
    setStatus(recipesStatus, "Please follow the formatting instructions!", true);
    input.focus();
    return;
  }
  input.value = ingredients.join(", ");
  document.querySelector("#recipes-results-title").textContent = "Recipes from your ingredients";
  recipeResults.replaceChildren();
  setStatus(recipesStatus, `Matching ${ingredients.join(", ")} against recipe ingredients…`);
  try {
    const lists = await Promise.all(ingredients.map(async (ingredient) => {
      const response = await fetch(`https://www.themealdb.com/api/json/v1/1/filter.php?i=${encodeURIComponent(ingredient)}`);
      if (!response.ok) throw new Error(`Could not search for “${ingredient}”.`);
      const data = await response.json();
      return (data.meals || []).map((meal) => meal.idMeal);
    }));
    const counts = new Map();
    lists.forEach((ids) => ids.forEach((id) => counts.set(id, (counts.get(id) || 0) + 1)));
    const rankedIds = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 35);
    if (!rankedIds.length) {
      renderRecipes([], { emptyMessage: "No matches found. Try broader ingredient names, such as “bean” instead of a specific brand." });
      return;
    }
    const idSet = new Set(rankedIds.map(([id]) => id));
    const details = await fetchMealDetails(rankedIds.map(([id]) => ({ idMeal: id })));
    const matches = details
      .filter((meal) => idSet.has(meal.idMeal) && fitsDiet(meal, selectedDiet))
      .map((meal) => {
        const found = ingredients.filter((ingredient) =>
          ingredientNames(meal).some((name) => name.includes(ingredient) || ingredient.includes(name))
        );
        return toRecipe(meal, {
          matchCount: found.length,
          matchedIngredients: found,
          diet: `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} search match`
        });
      })
      .sort((a, b) => b.matchCount - a.matchCount)
      .slice(0, 24);
    renderRecipes(matches, { emptyMessage: "We found recipes, but none passed the selected dietary ingredient check. Try switching diet or ingredients." });
  } catch (error) {
    setStatus(recipesStatus, `${error.message || "Ingredient search failed."} Check your connection and try again.`, true);
  }
}

function searchQuery(areaOrCoords) {
  const cuisine = document.querySelector("#restaurant-cuisine").value;
  const radius = document.querySelector("#restaurant-radius").value;
  return {
    ...areaOrCoords,
    diet: selectedRestaurantDiet,
    cuisine,
    radius_miles: Number(radius)
  };
}

function updateMap(label) {
  const mapWrap = document.querySelector("#places-map-wrap");
  const map = document.querySelector("#places-map");
  const openLink = document.querySelector("#open-map-link");
  const cuisine = document.querySelector("#restaurant-cuisine").value;
  const mapQuery = [selectedRestaurantDiet, cuisine, "restaurants near", label].filter(Boolean).join(" ");
  const encoded = encodeURIComponent(mapQuery);
  map.src = `https://www.google.com/maps?q=${encoded}&output=embed`;
  openLink.href = `https://www.google.com/maps/search/?api=1&query=${encoded}`;
  mapWrap.hidden = selectedRestaurantView !== "map";
}

function showDirectoryMap(prefix, query) {
  const mapWrap = document.querySelector(`#${prefix}-map-wrap`);
  const map = document.querySelector(`#${prefix}-map`);
  const mapLink = document.querySelector(`#${prefix}-map-link`);
  const encoded = encodeURIComponent(query);
  map.src = `https://www.google.com/maps?q=${encoded}&output=embed`;
  mapLink.href = `https://www.google.com/maps/search/?api=1&query=${encoded}`;
  mapWrap.hidden = false;
}

function setDirectoryView(mode, group) {
  const selector = group === "restaurant"
    ? "[data-restaurant-view]"
    : `[data-directory-view="${group}"]`;
  document.querySelectorAll(selector).forEach((button) => {
    const active = (group === "restaurant" ? button.dataset.restaurantView : button.dataset.view) === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (group === "restaurant") {
    selectedRestaurantView = mode;
    if (mode === "list") {
      document.querySelector("#places-map-wrap").hidden = true;
      if (restaurantPlaces.length) openDirectoryList(`Restaurants near ${lastRestaurantLocation}`, restaurantPlaces, "Restaurant");
      else closeDirectoryList();
    }
    else {
      closeDirectoryList();
      if (lastRestaurantLocation) updateMap(lastRestaurantLocation);
    }
    return;
  }
  const search = directorySearches[group];
  if (!search) return;
  if (mode === "list") {
    document.querySelector(`#${group}-map-wrap`).hidden = true;
    openDirectoryList(search.title, search.places, search.categories.join(", "));
  } else {
    closeDirectoryList();
    showDirectoryMap(group, search.query);
  }
}

function openDirectoryList(title, places, typeFallback) {
  const modal = document.querySelector("#directory-list-modal");
  const content = document.querySelector("#directory-list-content");
  document.querySelector("#directory-list-title").textContent = title;
  content.replaceChildren();
  if (!places.length) {
    const empty = document.createElement("p");
    empty.className = "status-box";
    empty.textContent = "No matching places were returned for this search.";
    content.append(empty);
  }
  places.forEach((place) => {
    const row = document.createElement("article");
    row.className = "directory-list-row";
    const hours = Array.isArray(place.hours) && place.hours.length
      ? place.hours.join(" · ")
      : "Hours not listed by Google";
    const mapsUrl = place.googleMapsUri && /^https:\/\/(maps|www)\.google\.com\//i.test(place.googleMapsUri)
      ? place.googleMapsUri
      : "";
    row.innerHTML = `
      <div class="directory-list-main"><strong>${escapeHtml(place.name || "Local place")}</strong><span>${escapeHtml(place.primaryType || typeFallback)}</span></div>
      <div class="directory-list-field"><small>ADDRESS</small><span>${escapeHtml(place.address || "Address not listed")}</span></div>
      <div class="directory-list-field"><small>HOURS</small><span>${escapeHtml(hours)}</span></div>
      <div class="directory-list-field"><small>PHONE</small><span>${place.phone ? `<a href="tel:${escapeHtml(place.phone)}">${escapeHtml(place.phone)}</a>` : "Not listed by Google"}</span></div>
      ${mapsUrl ? `<a class="text-link" href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener noreferrer">Open in Google Maps ↗</a>` : ""}`;
    content.append(row);
  });
  modal.hidden = false;
  document.body.classList.add("directory-list-open");
  document.querySelector('[data-close-directory-list]:not(.directory-list-scrim)').focus();
}

function closeDirectoryList() {
  const modal = document.querySelector("#directory-list-modal");
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("directory-list-open");
}

function getPlacesErrorMessage(error) {
  if (window.location.protocol === "file:") {
    return "This page was opened as a file. Start the backend and open http://localhost:8000 (see README) to use Google Places.";
  }
  if (error instanceof TypeError) {
    return "Can’t reach the restaurant search backend. Start it with the README instructions and open this app at http://localhost:8000.";
  }
  return error.message || "Nearby places could not be loaded.";
}

async function searchNearbyPlaces(search, locationLabel) {
  restaurantResults.replaceChildren();
  restaurantPlaces = [];
  lastRestaurantLocation = locationLabel;
  closeDirectoryList();
  document.querySelector("#places-map-wrap").hidden = true;
  setStatus(restaurantsStatus, `Searching for ${selectedRestaurantDiet} restaurants near ${locationLabel}…`);
  updateMap(locationLabel);
  try {
    if (window.location.protocol === "file:") throw new Error("Restaurant search needs the backend server.");
    const response = await fetch("/api/places/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(searchQuery(search))
    });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("The restaurant search backend isn’t responding. Start it with the README instructions and open this app at http://localhost:8000.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The nearby places service is temporarily unavailable.");
    const uniquePlaces = [...new Map((result.places || []).filter((place) => place.id).map((place) => [place.id, place])).values()];
    restaurantPlaces = uniquePlaces;
    lastRestaurantLocation = locationLabel;
    document.querySelector("#places-heading").textContent = uniquePlaces.length ? `Plant-friendly places near ${locationLabel}.` : "No nearby matches yet.";
    document.querySelector("#places-meta").textContent = `${uniquePlaces.length} Google Maps result${uniquePlaces.length === 1 ? "" : "s"}`;
    if (!uniquePlaces.length) {
      setStatus(restaurantsStatus, `No ${selectedRestaurantDiet} restaurant matches were found near ${locationLabel}. Try a nearby area or broader search term.`, true);
      return;
    }
    if (selectedRestaurantView === "list") {
      openDirectoryList(`Restaurants near ${locationLabel}`, uniquePlaces, "Restaurant");
    }
    setStatus(restaurantsStatus, `${uniquePlaces.length} result${uniquePlaces.length === 1 ? "" : "s"} for ${selectedRestaurantDiet} restaurants near ${locationLabel}. Select one for details.`);
    uniquePlaces.forEach((place) => {
      const card = document.createElement("article");
      card.className = "restaurant-card";
      const name = place.name || "Restaurant";
      const rating = place.rating ? `${Number(place.rating).toFixed(1)} ★${place.userRatingCount ? ` (${Number(place.userRatingCount).toLocaleString()})` : ""}` : "";
      card.innerHTML = `
        <span class="restaurant-icon" aria-hidden="true">✳</span>
        <div class="restaurant-info"><strong>${escapeHtml(name)}</strong><div class="restaurant-details">
          <span class="tag">${escapeHtml(selectedRestaurantDiet)} search</span>
          ${place.primaryType ? `<span>${escapeHtml(place.primaryType)}</span>` : ""}
          ${place.address ? `<span>${escapeHtml(place.address)}</span>` : ""}
        </div></div>
        ${rating ? `<span class="restaurant-distance">${escapeHtml(rating)}</span>` : ""}
        <button class="icon-button restaurant-favorite" type="button" aria-label="Add ${escapeHtml(name)} to favorites" aria-pressed="false">♡</button>
        <button class="icon-button" type="button" aria-label="Preview ${escapeHtml(name)}">↗</button>`;
      const favoriteButton = card.querySelector(".restaurant-favorite");
      const isFavorite = favoriteRestaurants.some((saved) => saved.id === place.id);
      favoriteButton.classList.toggle("is-favorite", isFavorite);
      favoriteButton.setAttribute("aria-pressed", String(isFavorite));
      favoriteButton.setAttribute("aria-label", `${isFavorite ? "Remove" : "Add"} ${name} ${isFavorite ? "from" : "to"} favorites`);
      favoriteButton.textContent = isFavorite ? "♥" : "♡";
      favoriteButton.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleRestaurantFavorite(place, favoriteButton);
      });
      card.addEventListener("click", () => openRestaurant(place));
      restaurantResults.append(card);
    });
  } catch (error) {
    setStatus(restaurantsStatus, getPlacesErrorMessage(error), true);
  }
}

function findPlacesByArea(event) {
  event.preventDefault();
  const input = document.querySelector("#area-search-input");
  const area = input.value.trim();
  if (!area) {
    input.focus();
    return;
  }
  const button = document.querySelector("#area-search-form button");
  button.disabled = true;
  button.innerHTML = "Searching <span aria-hidden=\"true\">…</span>";
  document.querySelector("#places-meta").textContent = `Search area: ${area}`;
  searchNearbyPlaces({ area }, area).finally(() => {
    button.disabled = false;
    button.innerHTML = "Search area <span aria-hidden=\"true\">→</span>";
  });
}

function findNearbyPlaces() {
  const button = document.querySelector("#find-places-button");
  if (!navigator.geolocation) {
    setStatus(restaurantsStatus, "This browser doesn’t provide location access. Search by city or ZIP instead.", true);
    return;
  }
  if (window.location.protocol !== "https:" && window.location.hostname !== "localhost") {
    setStatus(restaurantsStatus, "Browser location requires a secure page. Open this site on localhost or HTTPS, or search by city or ZIP.", true);
    return;
  }
  button.disabled = true;
  button.innerHTML = "Finding nearby places <span aria-hidden=\"true\">…</span>";
  setStatus(restaurantsStatus, "Requesting your location… If this takes too long, search by city or ZIP below.");
  navigator.geolocation.getCurrentPosition((position) => {
    const { latitude, longitude } = position.coords;
    document.querySelector("#places-meta").textContent = "Location is only used for this search";
    searchNearbyPlaces({ latitude, longitude }, "your location").finally(() => {
      button.disabled = false;
      button.innerHTML = "Use my location <span aria-hidden=\"true\">→</span>";
    });
  }, (error) => {
    const message = error.code === error.PERMISSION_DENIED
      ? "Location access was denied. Allow it in your browser or device settings, or search by city or ZIP below."
      : error.code === error.POSITION_UNAVAILABLE
        ? "Your device couldn’t determine your location. Check device location services, or search by city or ZIP below."
        : "Your location didn’t arrive in time. Try again, check device location services, or search by city or ZIP below.";
    setStatus(restaurantsStatus, message, true);
    button.disabled = false;
    button.innerHTML = "Use my location <span aria-hidden=\"true\">→</span>";
  }, { enableHighAccuracy: false, timeout: 45000, maximumAge: 600000 });
}

function setReportRange(range) {
  const reportSamples = {
    week: { co2: "8.4", land: "12.6", cost: "$18", bars: [28, 35, 24], label: "Compared with a typical meal pattern" },
    month: { co2: "33.6", land: "50.4", cost: "$72", bars: [48, 54, 42], label: "Illustrative month, scaled from sample week" },
    year: { co2: "403", land: "605", cost: "$936", bars: [74, 81, 69], label: "Illustrative year, scaled from sample week" }
  };
  const sample = reportSamples[range];
  if (!sample) return;
  selectedRange = range;
  document.querySelectorAll("[data-range]").forEach((button) => {
    const active = button.dataset.range === range;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelector("#report-co2").innerHTML = `${sample.co2} <small>kg CO₂e</small>`;
  document.querySelector("#report-land").innerHTML = `${sample.land} <small>m²·year</small>`;
  document.querySelector("#report-cost").innerHTML = `${sample.cost} <small>modeled</small>`;
  document.querySelector("#co2-bar").style.width = `${sample.bars[0]}%`;
  document.querySelector("#land-bar").style.width = `${sample.bars[1]}%`;
  document.querySelector("#cost-bar").style.width = `${sample.bars[2]}%`;
  document.querySelector("#report-co2-caption").textContent = sample.label;
}

function updateFarmLinks(silent = false) {
  const area = document.querySelector("#farm-area").value.trim();
  const radiusValues = [10, 25, 50, 75, 100];
  const radius = radiusValues[Number(document.querySelector("#farm-radius").value)] || 10;
  const categories = [...document.querySelectorAll('input[name="farm-category"]:checked')].map((input) => input.value);
  const status = document.querySelector("#farm-status");
  if (!area) {
    document.querySelector("#farm-area").focus();
    document.querySelector("#farm-map-wrap").hidden = true;
    document.querySelector("#farm-map").removeAttribute("src");
    delete directorySearches.farm;
    closeDirectoryList();
    setStatus(status, "Add a city, state, or ZIP code to search local listings.", true);
    return;
  }
  const areaQuery = encodeURIComponent(area);
  document.querySelector("#farmers-market-link").href =
    "https://www.ams.usda.gov/local-food-directories/farmersmarkets";
  document.querySelector("#farm-directory-link").href =
    `https://www.google.com/maps/search/farms+and+CSA+near+${areaQuery}/`;
  document.querySelector("#grocery-directory-link").href =
    `https://www.google.com/maps/search/local+produce+groceries+near+${areaQuery}/`;
  searchDirectory("farm", area, radius, categories, silent);
}

async function searchDirectory(prefix, area, radius, categories, silent = false) {
  const status = document.querySelector(`#${prefix}-status`);
  const mapWrap = document.querySelector(`#${prefix}-map-wrap`);
  const selectedMode = document.querySelector(`[data-directory-view="${prefix}"][aria-pressed="true"]`)?.dataset.view || "map";
  mapWrap.hidden = true;
  closeDirectoryList();
  if (!categories.length) {
    document.querySelector(`#${prefix}-map`).removeAttribute("src");
    delete directorySearches[prefix];
    if (!document.querySelector("#directory-list-modal").hidden) closeDirectoryList();
    setStatus(status, "Select at least one category to display search results.", true);
    return;
  }
  if (window.location.protocol === "file:") {
    setStatus(status, "This page was opened as a file. Start the backend and open http://localhost:8000 (see README) to search Google Maps.", true);
    return;
  }
  setStatus(status, `Searching ${categories.join(", ")} near ${area}…`);
  try {
    const response = await fetch("/api/places/directory-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ area, radius_miles: radius, categories })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The local search service is unavailable.");
    const places = (result.places || []).filter((place) => place.id);
    const query = `${categories.join(", ")} near ${area} within ${radius} miles`;
    directorySearches[prefix] = {
      title: `${prefix === "farm" ? "Local food" : "Community opportunities"} near ${area}`,
      query,
      categories,
      places
    };
    if (selectedMode === "map") showDirectoryMap(prefix, query);
    else mapWrap.hidden = true;
    setStatus(status, places.length
      ? `${places.length} Google Maps result${places.length === 1 ? "" : "s"} for ${categories.join(", ")} near ${area}. Google may not enforce an exact radius or category boundary.`
      : `No Google Maps results were returned for ${categories.join(", ")} near ${area}.`);
    if (selectedMode === "list") {
      const typeFallback = categories.join(", ");
      openDirectoryList(`${prefix === "farm" ? "Local food" : "Community opportunities"} near ${area}`, places, typeFallback);
    }
    if (!silent && places.length) showToast(`${places.length} nearby result${places.length === 1 ? "" : "s"} found.`);
  } catch (error) {
    mapWrap.hidden = true;
    setStatus(status, error.message || "The local search could not be completed. Try again.", true);
  }
}

function findCommunityOpportunities() {
  const area = document.querySelector("#community-area").value.trim();
  const radiusValues = [10, 25, 50, 75, 100];
  const radius = radiusValues[Number(document.querySelector("#community-radius").value)] || 10;
  const categories = [...document.querySelectorAll('input[name="community-category"]:checked')].map((input) => input.value);
  if (!area) {
    document.querySelector("#community-area").focus();
    document.querySelector("#community-map-wrap").hidden = true;
    delete directorySearches.community;
    closeDirectoryList();
    setStatus(document.querySelector("#community-status"), "Add a city, state, or ZIP code to search local opportunities.", true);
    return;
  }
  searchDirectory("community", area, radius, categories);
}

function renderSurveyStep(direction = 1) {
  const steps = [...document.querySelectorAll("[data-survey-step]")];
  steps.forEach((step, index) => {
    const isCurrent = index === surveyStepIndex;
    step.hidden = !isCurrent;
    step.classList.toggle("active", isCurrent);
  });
  const titles = ["Choose your path.", "Follow your curiosity.", "Make room for your goals.", "What inspires you?", "A little context, if you like."];
  document.querySelector("#survey-title").textContent = titles[surveyStepIndex];
  document.querySelector("#survey-progress").textContent = `YOUR FOOD JOURNEY · STEP ${surveyStepIndex + 1} OF ${steps.length}`;
  document.querySelector("#survey-back").hidden = surveyStepIndex === 0;
  document.querySelector("#survey-next").hidden = surveyStepIndex === steps.length - 1;
  document.querySelector("#survey-finish").hidden = surveyStepIndex !== steps.length - 1;
  if (direction) {
    const current = steps[surveyStepIndex];
    current.classList.remove("arrive");
    requestAnimationFrame(() => current.classList.add("arrive"));
  }
}

function applySurveyPreferences() {
  surveyCuisines = [...document.querySelectorAll("[data-food-pref].selected")].map((button) => button.dataset.foodPref);
  selectedDiet = selectedSurveyDiet;
  document.querySelectorAll("[data-diet]").forEach((item) => {
    const active = item.dataset.diet === selectedDiet;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  selectedRestaurantDiet = selectedSurveyDiet;
  document.querySelectorAll("[data-restaurant-diet]").forEach((item) => {
    const active = item.dataset.restaurantDiet === selectedRestaurantDiet;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  if (surveyCuisines.length) {
    selectedCuisine = surveyCuisines[0];
    document.querySelectorAll("[data-cuisine]").forEach((item) => {
      const active = item.dataset.cuisine === selectedCuisine;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  }
  updateProfileDisplay();
}

function transitionSurveyStep(nextStep) {
  const steps = [...document.querySelectorAll("[data-survey-step]")];
  if (nextStep < 0 || nextStep >= steps.length || nextStep === surveyStepIndex) return;
  const outgoing = steps[surveyStepIndex];
  outgoing.classList.remove("arrive");
  outgoing.classList.add("leave");
  window.setTimeout(() => {
    outgoing.classList.remove("leave");
    surveyStepIndex = nextStep;
    renderSurveyStep();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, 160);
}

function saveFavorites(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.error(`Could not save ${key} to browser storage.`, error);
    showToast("Your favorites changed for this visit but could not be saved in this browser.");
    return false;
  }
}

function recipeFavoriteKey(recipe) {
  return String(recipe.idMeal || recipe.url || recipe.name);
}

function isRecipeFavorite(recipe) {
  const key = recipeFavoriteKey(recipe);
  return favoriteRecipes.some((saved) => recipeFavoriteKey(saved) === key);
}

function updateRecipeFavoriteButton() {
  const button = document.querySelector("#favorite-recipe");
  const favorite = activeRecipe && isRecipeFavorite(activeRecipe);
  button.classList.toggle("is-favorite", Boolean(favorite));
  button.setAttribute("aria-pressed", String(Boolean(favorite)));
  button.setAttribute("aria-label", favorite ? "Remove recipe from favorites" : "Add recipe to favorites");
  button.textContent = favorite ? "♥" : "♡";
}

function toggleRecipeFavorite() {
  if (!activeRecipe) return;
  if (isRecipeFavorite(activeRecipe)) {
    favoriteRecipes = favoriteRecipes.filter((recipe) => recipeFavoriteKey(recipe) !== recipeFavoriteKey(activeRecipe));
  } else {
    favoriteRecipes = [...favoriteRecipes, activeRecipe];
  }
  saveFavorites("rooted-favorite-recipes", favoriteRecipes);
  updateRecipeFavoriteButton();
  if (selectedCuisine === "Favorites") renderRecipes(favoriteRecipes);
  renderFavoriteLists();
}

function toggleRestaurantFavorite(place, button = null) {
  const exists = favoriteRestaurants.some((saved) => saved.id === place.id);
  favoriteRestaurants = exists
    ? favoriteRestaurants.filter((saved) => saved.id !== place.id)
    : [...favoriteRestaurants, {
      id: place.id,
      name: place.name || "Restaurant",
      address: place.address || "",
      googleMapsUri: place.googleMapsUri || "",
      websiteUri: place.websiteUri || "",
      rating: place.rating || null,
      userRatingCount: place.userRatingCount || null
    }];
  saveFavorites("rooted-favorite-restaurants", favoriteRestaurants);
  renderFavoriteLists();
  if (button) {
    const favorite = favoriteRestaurants.some((saved) => saved.id === place.id);
    button.classList.toggle("is-favorite", favorite);
    button.setAttribute("aria-pressed", String(favorite));
    button.textContent = favorite ? "♥" : "♡";
  }
}

function renderFavoriteLists() {
  const restaurantList = document.querySelector("#favorite-restaurants-list");
  const recipeList = document.querySelector("#favorite-recipes-list");
  restaurantList.replaceChildren();
  recipeList.replaceChildren();
  document.querySelector("#favorite-restaurants-empty").hidden = favoriteRestaurants.length > 0;
  document.querySelector("#favorite-recipes-empty").hidden = favoriteRecipes.length > 0;
  favoriteRestaurants.forEach((place) => {
    const card = document.createElement("article");
    card.className = "favorite-card";
    const mapsUrl = safeExternalUrl(place.googleMapsUri) || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name)}`;
    card.innerHTML = `<span class="favorite-card-image">⌖</span><strong>${escapeHtml(place.name)}</strong><small>${escapeHtml(place.address || "Address not listed")}</small><a class="text-link" href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener noreferrer">View on map ↗</a><button class="favorite-remove" type="button" aria-label="Remove ${escapeHtml(place.name)} from favorites">♥</button>`;
    card.querySelector(".favorite-remove").addEventListener("click", () => toggleRestaurantFavorite(place));
    restaurantList.append(card);
  });
  favoriteRecipes.forEach((recipe) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "favorite-card favorite-recipe-card";
    const image = safeExternalUrl(recipe.image);
    card.innerHTML = `${image ? `<img class="favorite-card-image" src="${escapeHtml(image)}" alt="" loading="lazy">` : `<span class="favorite-card-image">✳</span>`}<strong>${escapeHtml(recipe.name || "Recipe")}</strong><small>${escapeHtml(recipe.area || "Plant-forward")}</small><span class="text-link">View recipe</span><span class="favorite-remove" aria-hidden="true">♥</span>`;
    card.addEventListener("click", () => openRecipePreview(recipe, card));
    recipeList.append(card);
  });
}

function showProfileTab(name) {
  document.querySelectorAll("[data-profile-tab]").forEach((button) => {
    const active = button.dataset.profileTab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-profile-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.profilePanel !== name;
  });
}

function updateCostDiet(diet, button) {
  selectedCostDiet = diet;
  document.querySelectorAll("[data-cost-diet]").forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  document.querySelector("#diet-cost-copy").textContent = diet === "vegan"
    ? "Vegan patterns replace all animal foods with plant foods. In the 150-country model, vegan and vegetarian patterns were generally among the most affordable sustainable options."
    : "Vegetarian patterns replacing some animal foods with legumes and whole grains were among the most affordable sustainable patterns in a 150-country model.";
}

document.querySelector("#open-signin").addEventListener("click", () => showAuth(false));
document.querySelector("#open-signup").addEventListener("click", () => showAuth(true));
document.querySelector("#landing-signup-link").addEventListener("click", () => showAuth(true));
document.querySelectorAll("[data-show-landing]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    showScreen("landing");
  });
});
document.querySelectorAll("[data-launch-survey]").forEach((button) => button.addEventListener("click", () => showSurvey(false)));
document.querySelector("#launch-demo").addEventListener("click", () => showSurvey(false));
document.querySelectorAll("[data-enter-app]").forEach((button) => button.addEventListener("click", () => {
  applySurveyPreferences();
  enterApp(returnToAppAfterSurvey ? activePage : "home");
}));
document.querySelector("#auth-form").addEventListener("submit", handleAuthSubmit);
document.querySelector("#toggle-auth-mode").addEventListener("click", () => {
  setAuthMode(document.querySelector("#signup-fields").hidden);
});
document.querySelector("#forgot-password").addEventListener("click", () => {
  document.querySelector("#auth-message").textContent = "Password reset email isn’t connected in this preview. Nothing has been sent.";
});
document.querySelector("#survey-form").addEventListener("submit", (event) => {
  event.preventDefault();
  applySurveyPreferences();
  enterApp(returnToAppAfterSurvey ? activePage : "home");
});
document.querySelector("#survey-next").addEventListener("click", () => transitionSurveyStep(surveyStepIndex + 1));
document.querySelector("#survey-back").addEventListener("click", () => transitionSurveyStep(surveyStepIndex - 1));
document.querySelectorAll("[data-survey-diet]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedSurveyDiet = button.dataset.surveyDiet;
    document.querySelectorAll("[data-survey-diet]").forEach((option) => {
      const active = option === button;
      option.classList.toggle("selected", active);
      option.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-food-pref]").forEach((button) => {
  button.addEventListener("click", () => {
    button.classList.toggle("selected");
    button.setAttribute("aria-pressed", String(button.classList.contains("selected")));
  });
});
document.querySelectorAll("[data-page]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    setPage(button.dataset.page);
  });
});
document.querySelectorAll("[data-open-page]").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.openPage));
});
document.querySelector("#methodology-button").addEventListener("click", sourcePreview);
document.querySelector("#close-preview").addEventListener("click", closePreview);
document.querySelector("#sidebar-toggle").addEventListener("click", (event) => {
  const button = event.currentTarget;
  const collapsed = document.body.classList.toggle("sidebar-collapsed");
  button.setAttribute("aria-expanded", String(!collapsed));
  button.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
  button.title = collapsed ? "Expand navigation" : "Collapse navigation";
  button.querySelector("span").textContent = collapsed ? "›" : "‹";
});
document.querySelector("#report-survey-link").addEventListener("click", () => showSurvey(true));
document.querySelector("#find-places-button").addEventListener("click", findNearbyPlaces);
document.querySelector("#area-search-form").addEventListener("submit", findPlacesByArea);
document.querySelector("#browse-recipes-button").addEventListener("click", browseCuisine);
document.querySelector("#ingredients-form").addEventListener("submit", findRecipesByIngredients);
document.querySelector("#farm-search-button").addEventListener("click", updateFarmLinks);
document.querySelector("#community-search-button").addEventListener("click", findCommunityOpportunities);
document.querySelectorAll("[data-restaurant-view]").forEach((button) => {
  button.addEventListener("click", () => setDirectoryView(button.dataset.restaurantView, "restaurant"));
});
document.querySelectorAll("[data-directory-view]").forEach((button) => {
  button.addEventListener("click", () => setDirectoryView(button.dataset.view, button.dataset.directoryView));
});
document.querySelectorAll("[data-close-directory-list]").forEach((button) => {
  button.addEventListener("click", closeDirectoryList);
});
document.querySelector("#print-directory-list").addEventListener("click", () => window.print());
document.querySelector("#farm-radius").addEventListener("input", (event) => {
  const distances = [10, 25, 50, 75, 100];
  document.querySelector("#farm-radius-output").textContent = `${distances[Number(event.currentTarget.value)]} miles`;
  if (directorySearches.farm) updateFarmLinks(true);
});
document.querySelector("#community-radius").addEventListener("input", (event) => {
  const distances = [10, 25, 50, 75, 100];
  document.querySelector("#community-radius-output").textContent = `${distances[Number(event.currentTarget.value)]} miles`;
  if (directorySearches.community) findCommunityOpportunities();
});
document.querySelector("#favorite-recipe").addEventListener("click", toggleRecipeFavorite);
document.querySelector("#print-recipe").addEventListener("click", () => window.print());
document.querySelectorAll("[data-profile-tab]").forEach((button) => {
  button.addEventListener("click", () => showProfileTab(button.dataset.profileTab));
});
document.querySelector("#edit-preferences").addEventListener("click", () => {
  showSurvey(false);
});
document.querySelector("#logout-button").addEventListener("click", () => {
  demoProfile = { firstName: "", lastName: "", email: "", birthday: "", address: "" };
  updateProfileDisplay();
  showScreen("landing");
});
document.querySelectorAll("[data-demo-action]").forEach((button) => {
  button.addEventListener("click", () => showToast(button.dataset.demoAction));
});
document.querySelectorAll("[data-range]").forEach((button) => button.addEventListener("click", () => setReportRange(button.dataset.range)));
document.querySelectorAll("[data-cost-diet]").forEach((button) => button.addEventListener("click", () => updateCostDiet(button.dataset.costDiet, button)));
document.querySelectorAll("[data-diet]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedDiet = button.dataset.diet;
    document.querySelectorAll("[data-diet]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-restaurant-diet]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedRestaurantDiet = button.dataset.restaurantDiet;
    document.querySelectorAll("[data-restaurant-diet]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-cuisine]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedCuisine = button.dataset.cuisine;
    document.querySelectorAll("[data-cuisine]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-close-recipe]").forEach((button) => button.addEventListener("click", closeRecipePreview));
favoriteRecipes = readFavorites("rooted-favorite-recipes");
favoriteRestaurants = readFavorites("rooted-favorite-restaurants");
document.querySelectorAll('input[name="farm-category"]').forEach((input) => input.addEventListener("change", () => {
  if (directorySearches.farm) updateFarmLinks(true);
}));
document.querySelectorAll('input[name="community-category"]').forEach((input) => input.addEventListener("change", () => {
  if (!document.querySelectorAll('input[name="community-category"]:checked').length) {
    document.querySelector("#community-map-wrap").hidden = true;
    document.querySelector("#community-map").removeAttribute("src");
    delete directorySearches.community;
    if (!document.querySelector("#directory-list-modal").hidden) closeDirectoryList();
    setStatus(document.querySelector("#community-status"), "Select at least one community category to display search results.");
  } else if (directorySearches.community) {
    findCommunityOpportunities();
  }
}));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closePreview();
    closeRecipePreview();
    closeDirectoryList();
  }
});

setReportRange(selectedRange);
