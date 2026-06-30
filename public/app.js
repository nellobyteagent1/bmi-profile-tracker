import 'https://esm.sh/zone.js@0.15.1';
import 'https://esm.sh/@angular/compiler@20.3.5';
import { Component, signal } from 'https://esm.sh/@angular/core@20.3.5';
import { bootstrapApplication } from 'https://esm.sh/@angular/platform-browser@20.3.5';
import { CommonModule } from 'https://esm.sh/@angular/common@20.3.5';
import { FormsModule } from 'https://esm.sh/@angular/forms@20.3.5';

const apiBase = window.__APP_CONFIG__?.apiBase || '';

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || 'Request failed.');
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

class AppComponent {
  loading = signal(true);
  error = signal('');
  success = signal('');
  mode = signal('login');
  authView = signal(false);
  bmi = signal(null);
  user = signal(null);
  registerForm = {
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    age: 25,
    gender: 'Male',
    heightCm: 170,
    weightKg: 70,
  };
  loginForm = {
    email: '',
    password: '',
  };
  profileForm = {
    firstName: '',
    lastName: '',
    age: 25,
    gender: 'Male',
    heightCm: 170,
    weightKg: 70,
  };
  fieldErrors = {};

  constructor() {
    this.restore();
  }

  clearMessages() {
    this.error.set('');
    this.success.set('');
    this.fieldErrors = {};
  }

  async restore() {
    try {
      const payload = await request('/api/me');
      this.applySession(payload);
    } catch {
      this.authView.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  applySession(payload) {
    this.user.set(payload.user);
    this.bmi.set(payload.bmi);
    this.profileForm = {
      firstName: payload.user.firstName,
      lastName: payload.user.lastName,
      age: payload.user.age,
      gender: payload.user.gender,
      heightCm: payload.user.heightCm,
      weightKg: payload.user.weightKg,
    };
    this.authView.set(false);
  }

  async register() {
    this.clearMessages();
    try {
      const payload = await request('/api/register', {
        method: 'POST',
        body: JSON.stringify(this.registerForm),
      });
      this.applySession(payload);
      this.success.set('Account created and profile saved.');
    } catch (error) {
      this.fieldErrors = error.payload?.fieldErrors || {};
      this.error.set(error.message);
    }
  }

  async login() {
    this.clearMessages();
    try {
      const payload = await request('/api/login', {
        method: 'POST',
        body: JSON.stringify(this.loginForm),
      });
      this.applySession(payload);
      this.success.set('Welcome back. Saved profile loaded.');
    } catch (error) {
      this.error.set(error.message);
    }
  }

  async saveProfile() {
    this.clearMessages();
    try {
      const payload = await request('/api/profile', {
        method: 'PUT',
        body: JSON.stringify(this.profileForm),
      });
      this.applySession(payload);
      this.success.set('Profile updated.');
    } catch (error) {
      this.fieldErrors = error.payload?.fieldErrors || {};
      this.error.set(error.message);
    }
  }

  async logout() {
    await request('/api/logout', { method: 'POST', body: '{}' });
    this.user.set(null);
    this.bmi.set(null);
    this.mode.set('login');
    this.authView.set(true);
    this.success.set('Signed out.');
  }

  categoryClass() {
    const category = this.bmi()?.category || '';
    return category.toLowerCase();
  }
}

Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <main class="shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Angular BMI Tracker</p>
          <h1>Save your profile once, then come back to your BMI dashboard anytime.</h1>
          <p class="intro">
            Register your details, sign in on later visits, and keep your BMI result ready without re-entering your profile.
          </p>
        </div>
        <div class="hero-card">
          <div class="status" *ngIf="loading()">Checking saved session...</div>
          <div *ngIf="!loading() && authView()">
            <div class="tab-row">
              <button [class.active]="mode()==='login'" (click)="mode.set('login')">Login</button>
              <button [class.active]="mode()==='register'" (click)="mode.set('register')">Register</button>
            </div>

            <form class="panel" *ngIf="mode()==='login'" (ngSubmit)="login()">
              <label>Email
                <input type="email" [(ngModel)]="loginForm.email" name="loginEmail" required>
              </label>
              <label>Password
                <input type="password" [(ngModel)]="loginForm.password" name="loginPassword" required minlength="8">
              </label>
              <button class="primary" type="submit">Login</button>
            </form>

            <form class="panel register" *ngIf="mode()==='register'" (ngSubmit)="register()">
              <div class="grid two">
                <label>First name
                  <input [(ngModel)]="registerForm.firstName" name="firstName" required>
                  <span class="field-error">{{ fieldErrors.firstName }}</span>
                </label>
                <label>Last name
                  <input [(ngModel)]="registerForm.lastName" name="lastName" required>
                  <span class="field-error">{{ fieldErrors.lastName }}</span>
                </label>
              </div>
              <div class="grid two">
                <label>Email
                  <input type="email" [(ngModel)]="registerForm.email" name="email" required>
                  <span class="field-error">{{ fieldErrors.email }}</span>
                </label>
                <label>Password
                  <input type="password" [(ngModel)]="registerForm.password" name="password" required minlength="8">
                  <span class="field-error">{{ fieldErrors.password }}</span>
                </label>
              </div>
              <div class="grid three">
                <label>Age
                  <input type="number" [(ngModel)]="registerForm.age" name="age" min="13" max="120" required>
                  <span class="field-error">{{ fieldErrors.age }}</span>
                </label>
                <label>Gender
                  <select [(ngModel)]="registerForm.gender" name="gender" required>
                    <option>Male</option>
                    <option>Female</option>
                    <option>Other</option>
                  </select>
                  <span class="field-error">{{ fieldErrors.gender }}</span>
                </label>
                <label>Height (cm)
                  <input type="number" [(ngModel)]="registerForm.heightCm" name="heightCm" min="80" max="260" step="0.1" required>
                  <span class="field-error">{{ fieldErrors.heightCm }}</span>
                </label>
              </div>
              <label>Weight (kg)
                <input type="number" [(ngModel)]="registerForm.weightKg" name="weightKg" min="20" max="500" step="0.1" required>
                <span class="field-error">{{ fieldErrors.weightKg }}</span>
              </label>
              <button class="primary" type="submit">Create account</button>
            </form>
          </div>

          <div class="message error" *ngIf="error()">{{ error() }}</div>
          <div class="message success" *ngIf="success()">{{ success() }}</div>
        </div>
      </section>

      <section class="dashboard" *ngIf="user() as activeUser">
        <div class="profile-card">
          <div class="card-header">
            <div>
              <p class="eyebrow">Saved profile</p>
              <h2>{{ activeUser.firstName }} {{ activeUser.lastName }}</h2>
              <p>{{ activeUser.email }}</p>
            </div>
            <button class="ghost" (click)="logout()">Logout</button>
          </div>

          <form class="panel" (ngSubmit)="saveProfile()">
            <div class="grid two">
              <label>First name
                <input [(ngModel)]="profileForm.firstName" name="profileFirstName" required>
              </label>
              <label>Last name
                <input [(ngModel)]="profileForm.lastName" name="profileLastName" required>
              </label>
            </div>
            <div class="grid three">
              <label>Age
                <input type="number" [(ngModel)]="profileForm.age" name="profileAge" min="13" max="120" required>
              </label>
              <label>Gender
                <select [(ngModel)]="profileForm.gender" name="profileGender" required>
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </label>
              <label>Height (cm)
                <input type="number" [(ngModel)]="profileForm.heightCm" name="profileHeightCm" min="80" max="260" step="0.1" required>
              </label>
            </div>
            <label>Weight (kg)
              <input type="number" [(ngModel)]="profileForm.weightKg" name="profileWeightKg" min="20" max="500" step="0.1" required>
            </label>
            <button class="primary" type="submit">Recalculate BMI</button>
          </form>
        </div>

        <div class="result-card" *ngIf="bmi() as currentBmi">
          <p class="eyebrow">BMI result</p>
          <div class="bmi-number">{{ currentBmi.value }}</div>
          <div class="bmi-pill" [class]="categoryClass()">{{ currentBmi.category }}</div>
          <dl class="facts">
            <div><dt>Height</dt><dd>{{ activeUser.heightCm }} cm</dd></div>
            <div><dt>Weight</dt><dd>{{ activeUser.weightKg }} kg</dd></div>
            <div><dt>Age</dt><dd>{{ activeUser.age }}</dd></div>
            <div><dt>Gender</dt><dd>{{ activeUser.gender }}</dd></div>
          </dl>
        </div>
      </section>
    </main>
  `,
})(AppComponent);

bootstrapApplication(AppComponent);
