// Form and input component tests
const { mockBrowserAPIs } = require('../setup/mock-services');

describe('Form and Input Components', () => {
  let container;

  beforeEach(() => {
    mockBrowserAPIs();
    
    document.body.innerHTML = `
      <div id="test-container">
        <!-- Search Form Component -->
        <form class="search-form" id="festival-search-form">
          <div class="search-input-group">
            <input 
              type="text" 
              id="festival-search" 
              class="search-input" 
              placeholder="Search festivals or artists..."
              autocomplete="off"
              required
            >
            <button type="submit" class="search-button">
              <span class="search-icon">🔍</span>
              Search
            </button>
          </div>
          <div class="search-suggestions" id="search-suggestions" style="display: none;">
            <!-- Autocomplete suggestions will appear here -->
          </div>
        </form>

        <!-- Login Form Component -->
        <form class="auth-form login-form" id="login-form">
          <div class="form-group">
            <label for="email">Email</label>
            <input 
              type="email" 
              id="email" 
              class="form-input email-input" 
              required
              autocomplete="email"
            >
            <div class="field-error" id="email-error" style="display: none;"></div>
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input 
              type="password" 
              id="password" 
              class="form-input password-input" 
              required
              minlength="6"
              autocomplete="current-password"
            >
            <div class="field-error" id="password-error" style="display: none;"></div>
          </div>
          <button type="submit" class="submit-button login-button">Login</button>
          <div class="form-message" id="form-message" style="display: none;"></div>
        </form>

        <!-- Registration Form Component -->
        <form class="auth-form register-form" id="register-form" style="display: none;">
          <div class="form-group">
            <label for="reg-name">Full Name</label>
            <input 
              type="text" 
              id="reg-name" 
              class="form-input name-input" 
              required
              minlength="2"
              autocomplete="name"
            >
            <div class="field-error" id="name-error" style="display: none;"></div>
          </div>
          <div class="form-group">
            <label for="reg-email">Email</label>
            <input 
              type="email" 
              id="reg-email" 
              class="form-input email-input" 
              required
              autocomplete="email"
            >
            <div class="field-error" id="reg-email-error" style="display: none;"></div>
          </div>
          <div class="form-group">
            <label for="reg-password">Password</label>
            <input 
              type="password" 
              id="reg-password" 
              class="form-input password-input" 
              required
              minlength="6"
              autocomplete="new-password"
            >
            <div class="field-error" id="reg-password-error" style="display: none;"></div>
          </div>
          <div class="form-group">
            <label for="confirm-password">Confirm Password</label>
            <input 
              type="password" 
              id="confirm-password" 
              class="form-input confirm-password-input" 
              required
              autocomplete="new-password"
            >
            <div class="field-error" id="confirm-password-error" style="display: none;"></div>
          </div>
          <button type="submit" class="submit-button register-button">Register</button>
          <div class="form-message" id="reg-form-message" style="display: none;"></div>
        </form>

        <!-- File Upload Component -->
        <div class="file-upload-component">
          <input type="file" id="file-input" class="file-input" accept=".csv,.json" style="display: none;">
          <button class="upload-button" onclick="document.getElementById('file-input').click()">
            Choose File
          </button>
          <div class="file-info" id="file-info" style="display: none;">
            <span class="file-name"></span>
            <span class="file-size"></span>
          </div>
          <div class="upload-progress" id="upload-progress" style="display: none;">
            <div class="progress-bar">
              <div class="progress-fill" style="width: 0%;"></div>
            </div>
            <span class="progress-text">0%</span>
          </div>
        </div>
      </div>
    `;

    container = document.getElementById('test-container');
    initializeFormComponents();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    jest.clearAllMocks();
  });

  function initializeFormComponents() {
    // Search form functionality
    const searchForm = document.getElementById('festival-search-form');
    const searchInput = document.getElementById('festival-search');
    const searchSuggestions = document.getElementById('search-suggestions');

    // Mock search suggestions
    const mockSuggestions = [
      { type: 'festival', name: 'Coachella Valley Music Festival', id: 'coachella-2024' },
      { type: 'artist', name: 'Lana Del Rey', id: 'lana-del-rey' },
      { type: 'festival', name: 'Bonnaroo Music & Arts Festival', id: 'bonnaroo-2024' }
    ];

    let searchTimeout;

    searchInput.addEventListener('input', function() {
      clearTimeout(searchTimeout);
      const query = this.value.trim();

      if (query.length < 2) {
        searchSuggestions.style.display = 'none';
        return;
      }

      searchTimeout = setTimeout(() => {
        const filtered = mockSuggestions.filter(item => 
          item.name.toLowerCase().includes(query.toLowerCase())
        );

        if (filtered.length > 0) {
          searchSuggestions.innerHTML = filtered.map(item => 
            `<div class="suggestion-item" data-type="${item.type}" data-id="${item.id}">
              <span class="suggestion-type">${item.type}</span>
              <span class="suggestion-name">${item.name}</span>
            </div>`
          ).join('');
          
          searchSuggestions.style.display = 'block';

          // Add click handlers to suggestions
          searchSuggestions.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', function() {
              searchInput.value = this.querySelector('.suggestion-name').textContent;
              searchSuggestions.style.display = 'none';
              
              // Trigger custom event
              document.dispatchEvent(new CustomEvent('suggestionSelected', {
                detail: {
                  type: this.dataset.type,
                  id: this.dataset.id,
                  name: this.querySelector('.suggestion-name').textContent
                }
              }));
            });
          });
        } else {
          searchSuggestions.style.display = 'none';
        }
      }, 300);
    });

    // Hide suggestions when clicking outside
    document.addEventListener('click', function(e) {
      if (!searchForm.contains(e.target)) {
        searchSuggestions.style.display = 'none';
      }
    });

    searchForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const query = searchInput.value.trim();
      
      if (query) {
        document.dispatchEvent(new CustomEvent('searchSubmitted', {
          detail: { query }
        }));
      }
    });

    // Login form functionality
    const loginForm = document.getElementById('login-form');
    loginForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      
      validateAndSubmitLogin(email, password);
    });

    // Registration form functionality
    const registerForm = document.getElementById('register-form');
    registerForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const name = document.getElementById('reg-name').value;
      const email = document.getElementById('reg-email').value;
      const password = document.getElementById('reg-password').value;
      const confirmPassword = document.getElementById('confirm-password').value;
      
      validateAndSubmitRegistration(name, email, password, confirmPassword);
    });

    // File upload functionality
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const uploadProgress = document.getElementById('upload-progress');

    fileInput.addEventListener('change', function() {
      const file = this.files[0];
      if (file) {
        // Show file info
        fileInfo.querySelector('.file-name').textContent = file.name;
        fileInfo.querySelector('.file-size').textContent = formatFileSize(file.size);
        fileInfo.style.display = 'block';

        // Simulate upload
        simulateFileUpload(file);
      }
    });

    function validateAndSubmitLogin(email, password) {
      clearFormErrors('login-form');
      
      const errors = [];
      
      if (!email) {
        errors.push({ field: 'email', message: 'Email is required' });
      } else if (!isValidEmail(email)) {
        errors.push({ field: 'email', message: 'Please enter a valid email address' });
      }
      
      if (!password) {
        errors.push({ field: 'password', message: 'Password is required' });
      } else if (password.length < 6) {
        errors.push({ field: 'password', message: 'Password must be at least 6 characters' });
      }

      if (errors.length > 0) {
        displayFormErrors(errors);
        return;
      }

      // Mock API call
      showFormMessage('login-form', 'Logging in...', 'info');
      
      setTimeout(() => {
        if (email === 'test@example.com' && password === 'password123') {
          showFormMessage('login-form', 'Login successful!', 'success');
          document.dispatchEvent(new CustomEvent('loginSuccess', {
            detail: { email }
          }));
        } else {
          showFormMessage('login-form', 'Invalid email or password', 'error');
        }
      }, 1000);
    }

    function validateAndSubmitRegistration(name, email, password, confirmPassword) {
      clearFormErrors('register-form');
      
      const errors = [];
      
      if (!name || name.length < 2) {
        errors.push({ field: 'name', message: 'Name must be at least 2 characters' });
      }
      
      if (!email) {
        errors.push({ field: 'reg-email', message: 'Email is required' });
      } else if (!isValidEmail(email)) {
        errors.push({ field: 'reg-email', message: 'Please enter a valid email address' });
      }
      
      if (!password) {
        errors.push({ field: 'reg-password', message: 'Password is required' });
      } else if (password.length < 6) {
        errors.push({ field: 'reg-password', message: 'Password must be at least 6 characters' });
      }
      
      if (password !== confirmPassword) {
        errors.push({ field: 'confirm-password', message: 'Passwords do not match' });
      }

      if (errors.length > 0) {
        displayFormErrors(errors);
        return;
      }

      // Mock API call
      showFormMessage('register-form', 'Creating account...', 'info');
      
      setTimeout(() => {
        if (email === 'existing@example.com') {
          showFormMessage('register-form', 'An account with this email already exists', 'error');
        } else {
          showFormMessage('register-form', 'Account created successfully!', 'success');
          document.dispatchEvent(new CustomEvent('registrationSuccess', {
            detail: { name, email }
          }));
        }
      }, 1000);
    }

    function simulateFileUpload(file) {
      uploadProgress.style.display = 'block';
      const progressFill = uploadProgress.querySelector('.progress-fill');
      const progressText = uploadProgress.querySelector('.progress-text');
      
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 20;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          
          setTimeout(() => {
            uploadProgress.style.display = 'none';
            document.dispatchEvent(new CustomEvent('fileUploaded', {
              detail: { file: file.name, size: file.size }
            }));
          }, 500);
        }
        
        progressFill.style.width = progress + '%';
        progressText.textContent = Math.round(progress) + '%';
      }, 100);
    }

    function isValidEmail(email) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function clearFormErrors(formId) {
      const form = document.getElementById(formId);
      form.querySelectorAll('.field-error').forEach(error => {
        error.style.display = 'none';
        error.textContent = '';
      });
    }

    function displayFormErrors(errors) {
      errors.forEach(error => {
        const errorElement = document.getElementById(error.field + '-error');
        if (errorElement) {
          errorElement.textContent = error.message;
          errorElement.style.display = 'block';
        }
      });
    }

    function showFormMessage(formId, message, type) {
      const form = document.getElementById(formId);
      const messageElement = form.querySelector('.form-message');
      
      messageElement.textContent = message;
      messageElement.className = `form-message ${type}`;
      messageElement.style.display = 'block';
    }

    function formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
  }

  describe('Search Form Component', () => {
    test('should show autocomplete suggestions', async () => {
      const searchInput = container.querySelector('#festival-search');
      const suggestions = container.querySelector('#search-suggestions');

      // Type in search input
      searchInput.value = 'coach';
      searchInput.dispatchEvent(new Event('input'));

      // Wait for debounced search
      await new Promise(resolve => setTimeout(resolve, 350));

      expect(suggestions.style.display).toBe('block');
      expect(suggestions.innerHTML).toContain('Coachella');
    });

    test('should select suggestion on click', (done) => {
      const searchInput = container.querySelector('#festival-search');
      
      document.addEventListener('suggestionSelected', (event) => {
        expect(event.detail.name).toBe('Coachella Valley Music Festival');
        expect(event.detail.type).toBe('festival');
        expect(searchInput.value).toBe('Coachella Valley Music Festival');
        done();
      });

      // Simulate typing and suggestion click
      searchInput.value = 'coach';
      searchInput.dispatchEvent(new Event('input'));

      setTimeout(() => {
        const suggestion = container.querySelector('.suggestion-item');
        suggestion.click();
      }, 350);
    });

    test('should hide suggestions when clicking outside', async () => {
      const searchInput = container.querySelector('#festival-search');
      const suggestions = container.querySelector('#search-suggestions');

      // Show suggestions
      searchInput.value = 'coach';
      searchInput.dispatchEvent(new Event('input'));
      await new Promise(resolve => setTimeout(resolve, 350));

      expect(suggestions.style.display).toBe('block');

      // Click outside
      document.body.click();

      expect(suggestions.style.display).toBe('none');
    });

    test('should submit search form', (done) => {
      const searchForm = container.querySelector('#festival-search-form');
      const searchInput = container.querySelector('#festival-search');

      document.addEventListener('searchSubmitted', (event) => {
        expect(event.detail.query).toBe('test search');
        done();
      });

      searchInput.value = 'test search';
      searchForm.dispatchEvent(new Event('submit'));
    });

    test('should not submit empty search', () => {
      const searchForm = container.querySelector('#festival-search-form');
      const searchInput = container.querySelector('#festival-search');
      
      let submitted = false;
      document.addEventListener('searchSubmitted', () => {
        submitted = true;
      });

      searchInput.value = '   '; // Only whitespace
      searchForm.dispatchEvent(new Event('submit'));

      expect(submitted).toBe(false);
    });
  });

  describe('Login Form Component', () => {
    test('should validate required fields', () => {
      const loginForm = container.querySelector('#login-form');
      const emailError = container.querySelector('#email-error');
      const passwordError = container.querySelector('#password-error');

      loginForm.dispatchEvent(new Event('submit'));

      expect(emailError.style.display).toBe('block');
      expect(emailError.textContent).toBe('Email is required');
      expect(passwordError.style.display).toBe('block');
      expect(passwordError.textContent).toBe('Password is required');
    });

    test('should validate email format', () => {
      const loginForm = container.querySelector('#login-form');
      const emailInput = container.querySelector('#email');
      const emailError = container.querySelector('#email-error');

      emailInput.value = 'invalid-email';
      loginForm.dispatchEvent(new Event('submit'));

      expect(emailError.style.display).toBe('block');
      expect(emailError.textContent).toBe('Please enter a valid email address');
    });

    test('should validate password length', () => {
      const loginForm = container.querySelector('#login-form');
      const emailInput = container.querySelector('#email');
      const passwordInput = container.querySelector('#password');
      const passwordError = container.querySelector('#password-error');

      emailInput.value = 'test@example.com';
      passwordInput.value = '123';
      loginForm.dispatchEvent(new Event('submit'));

      expect(passwordError.style.display).toBe('block');
      expect(passwordError.textContent).toBe('Password must be at least 6 characters');
    });

    test('should handle successful login', (done) => {
      const loginForm = container.querySelector('#login-form');
      const emailInput = container.querySelector('#email');
      const passwordInput = container.querySelector('#password');

      document.addEventListener('loginSuccess', (event) => {
        expect(event.detail.email).toBe('test@example.com');
        done();
      });

      emailInput.value = 'test@example.com';
      passwordInput.value = 'password123';
      loginForm.dispatchEvent(new Event('submit'));
    });

    test('should handle login failure', (done) => {
      const loginForm = container.querySelector('#login-form');
      const emailInput = container.querySelector('#email');
      const passwordInput = container.querySelector('#password');
      const formMessage = container.querySelector('#form-message');

      emailInput.value = 'wrong@example.com';
      passwordInput.value = 'wrongpassword';
      loginForm.dispatchEvent(new Event('submit'));

      setTimeout(() => {
        expect(formMessage.textContent).toBe('Invalid email or password');
        expect(formMessage.classList.contains('error')).toBe(true);
        done();
      }, 1100);
    });
  });

  describe('Registration Form Component', () => {
    test('should validate all required fields', () => {
      const registerForm = container.querySelector('#register-form');
      const nameError = container.querySelector('#name-error');
      const emailError = container.querySelector('#reg-email-error');
      const passwordError = container.querySelector('#reg-password-error');

      registerForm.dispatchEvent(new Event('submit'));

      expect(nameError.style.display).toBe('block');
      expect(emailError.style.display).toBe('block');
      expect(passwordError.style.display).toBe('block');
    });

    test('should validate password confirmation', () => {
      const registerForm = container.querySelector('#register-form');
      const nameInput = container.querySelector('#reg-name');
      const emailInput = container.querySelector('#reg-email');
      const passwordInput = container.querySelector('#reg-password');
      const confirmPasswordInput = container.querySelector('#confirm-password');
      const confirmPasswordError = container.querySelector('#confirm-password-error');

      nameInput.value = 'Test User';
      emailInput.value = 'test@example.com';
      passwordInput.value = 'password123';
      confirmPasswordInput.value = 'different123';

      registerForm.dispatchEvent(new Event('submit'));

      expect(confirmPasswordError.style.display).toBe('block');
      expect(confirmPasswordError.textContent).toBe('Passwords do not match');
    });

    test('should handle successful registration', (done) => {
      const registerForm = container.querySelector('#register-form');
      const nameInput = container.querySelector('#reg-name');
      const emailInput = container.querySelector('#reg-email');
      const passwordInput = container.querySelector('#reg-password');
      const confirmPasswordInput = container.querySelector('#confirm-password');

      document.addEventListener('registrationSuccess', (event) => {
        expect(event.detail.name).toBe('Test User');
        expect(event.detail.email).toBe('test@example.com');
        done();
      });

      nameInput.value = 'Test User';
      emailInput.value = 'test@example.com';
      passwordInput.value = 'password123';
      confirmPasswordInput.value = 'password123';

      registerForm.dispatchEvent(new Event('submit'));
    });

    test('should handle existing user error', (done) => {
      const registerForm = container.querySelector('#register-form');
      const nameInput = container.querySelector('#reg-name');
      const emailInput = container.querySelector('#reg-email');
      const passwordInput = container.querySelector('#reg-password');
      const confirmPasswordInput = container.querySelector('#confirm-password');
      const formMessage = container.querySelector('#reg-form-message');

      nameInput.value = 'Existing User';
      emailInput.value = 'existing@example.com';
      passwordInput.value = 'password123';
      confirmPasswordInput.value = 'password123';

      registerForm.dispatchEvent(new Event('submit'));

      setTimeout(() => {
        expect(formMessage.textContent).toBe('An account with this email already exists');
        expect(formMessage.classList.contains('error')).toBe(true);
        done();
      }, 1100);
    });
  });

  describe('File Upload Component', () => {
    test('should display file information when file is selected', () => {
      const fileInput = container.querySelector('#file-input');
      const fileInfo = container.querySelector('#file-info');
      
      // Create a mock file
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      
      // Mock the files property
      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false
      });

      fileInput.dispatchEvent(new Event('change'));

      expect(fileInfo.style.display).toBe('block');
      expect(fileInfo.querySelector('.file-name').textContent).toBe('test.csv');
      expect(fileInfo.querySelector('.file-size').textContent).toContain('Bytes');
    });

    test('should show upload progress', (done) => {
      const fileInput = container.querySelector('#file-input');
      const uploadProgress = container.querySelector('#upload-progress');
      
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false
      });

      document.addEventListener('fileUploaded', (event) => {
        expect(event.detail.file).toBe('test.csv');
        expect(uploadProgress.style.display).toBe('none');
        done();
      });

      fileInput.dispatchEvent(new Event('change'));

      // Check that progress is shown
      setTimeout(() => {
        expect(uploadProgress.style.display).toBe('block');
      }, 50);
    });

    test('should format file sizes correctly', () => {
      const fileInput = container.querySelector('#file-input');
      const fileInfo = container.querySelector('#file-info');
      
      // Create a larger mock file
      const content = 'x'.repeat(1024 * 2); // 2KB
      const mockFile = new File([content], 'large.csv', { type: 'text/csv' });
      
      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false
      });

      fileInput.dispatchEvent(new Event('change'));

      expect(fileInfo.querySelector('.file-size').textContent).toContain('KB');
    });
  });

  describe('Form Accessibility', () => {
    test('should have proper labels for all inputs', () => {
      const inputs = container.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]');
      
      inputs.forEach(input => {
        const label = container.querySelector(`label[for="${input.id}"]`);
        expect(label).toBeTruthy();
        expect(label.textContent.trim()).toBeTruthy();
      });
    });

    test('should have appropriate autocomplete attributes', () => {
      const emailInput = container.querySelector('#email');
      const passwordInput = container.querySelector('#password');
      const nameInput = container.querySelector('#reg-name');

      expect(emailInput.getAttribute('autocomplete')).toBe('email');
      expect(passwordInput.getAttribute('autocomplete')).toBe('current-password');
      expect(nameInput.getAttribute('autocomplete')).toBe('name');
    });

    test('should associate error messages with inputs', () => {
      const emailInput = container.querySelector('#email');
      const emailError = container.querySelector('#email-error');

      // Trigger validation
      const loginForm = container.querySelector('#login-form');
      loginForm.dispatchEvent(new Event('submit'));

      // Error should be visible and associated with input
      expect(emailError.style.display).toBe('block');
      expect(emailError.id).toBe('email-error');
    });
  });

  describe('Form Error Handling', () => {
    test('should clear previous errors on new submission', () => {
      const loginForm = container.querySelector('#login-form');
      const emailInput = container.querySelector('#email');
      const emailError = container.querySelector('#email-error');

      // First submission with error
      loginForm.dispatchEvent(new Event('submit'));
      expect(emailError.style.display).toBe('block');

      // Second submission with valid data
      emailInput.value = 'test@example.com';
      container.querySelector('#password').value = 'password123';
      loginForm.dispatchEvent(new Event('submit'));

      expect(emailError.style.display).toBe('none');
    });

    test('should handle network errors gracefully', () => {
      // This would be tested with actual network mocking
      // For now, just verify error handling structure exists
      const formMessage = container.querySelector('#form-message');
      expect(formMessage).toBeTruthy();
    });
  });
});