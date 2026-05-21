import { Link } from 'react-router-dom';
import { GraduationCap, ArrowLeft } from 'lucide-react';

const EFFECTIVE_DATE = 'May 16, 2026';
const COMPANY_NAME = 'Enterprise Learning Platform';
const CONTACT_EMAIL = 'privacy@customlms.com';

export function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
            <GraduationCap className="h-5 w-5" />
            <span className="font-bold text-sm">{COMPANY_NAME}</span>
          </Link>
          <Link
            to="/"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors group"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
            Back to Login
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-6 py-12 pb-24">
        <div className="space-y-2 mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Legal</p>
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Privacy Policy</h1>
          <p className="text-muted-foreground text-sm">
            Effective date: <strong>{EFFECTIVE_DATE}</strong>
          </p>
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none space-y-10 text-foreground">

          <section className="space-y-3">
            <p className="text-muted-foreground leading-relaxed">
              {COMPANY_NAME} ("we," "our," or "us") is committed to protecting your personal information and your right to privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our learning management platform and related services (collectively, the "Services"). Please read this policy carefully. If you disagree with its terms, please discontinue use of our Services.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">1. Information We Collect</h2>
            <p className="text-muted-foreground leading-relaxed">
              We collect information in the following ways:
            </p>
            <h3 className="text-base font-semibold text-foreground">1.1 Information You Provide</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Account data:</strong> Name, email address, username, and password when you register.</li>
              <li><strong>Profile data:</strong> Job title, department, and profile photo if you choose to provide them.</li>
              <li><strong>Training data:</strong> Responses to assessments, quiz submissions, progress records, and completion statuses.</li>
              <li><strong>Communications:</strong> Messages or requests you send to support staff.</li>
            </ul>
            <h3 className="text-base font-semibold text-foreground">1.2 Information Collected Automatically</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Usage data:</strong> Pages viewed, features accessed, session duration, and navigation paths within the platform.</li>
              <li><strong>Device data:</strong> IP address, browser type and version, operating system, and screen resolution.</li>
              <li><strong>Log data:</strong> Server logs recording access times, referring URLs, and error events.</li>
              <li><strong>Cookies and similar technologies:</strong> Session cookies to maintain your authenticated state and optional analytics cookies where consented.</li>
            </ul>
            <h3 className="text-base font-semibold text-foreground">1.3 Information from Third Parties</h3>
            <p className="text-muted-foreground leading-relaxed">
              We may receive information about you from your employer (the "Organization") when they provision your account, including your name, email, and role within the organization.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">2. How We Use Your Information</h2>
            <p className="text-muted-foreground leading-relaxed">We use collected information to:</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Create and manage your account and provide access to the Services.</li>
              <li>Track and record your training progress, assessments, and certifications.</li>
              <li>Generate and issue certificates of completion on behalf of your Organization.</li>
              <li>Send transactional communications including enrollment confirmations, assignment notifications, and certificate issuance alerts.</li>
              <li>Provide customer support and respond to your inquiries.</li>
              <li>Ensure platform security and detect, prevent, or investigate fraud or unauthorized access.</li>
              <li>Analyze usage patterns to improve platform functionality and user experience.</li>
              <li>Comply with legal obligations and enforce our Terms of Service.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">3. Sharing and Disclosure of Information</h2>
            <p className="text-muted-foreground leading-relaxed">
              We do not sell your personal data. We may share your information in the following limited circumstances:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>With your Organization:</strong> Administrators and authorized managers within your employer's account may view your training records, completion status, and certificates as part of the B2B service we provide.</li>
              <li><strong>Service providers:</strong> Trusted third-party vendors who assist us in operating our platform (e.g., cloud hosting, email delivery, analytics), bound by confidentiality obligations.</li>
              <li><strong>Legal requirements:</strong> When required by law, regulation, court order, or governmental authority.</li>
              <li><strong>Business transfers:</strong> In connection with a merger, acquisition, or sale of assets, with notice provided to you.</li>
              <li><strong>Safety:</strong> To protect the rights, property, or safety of {COMPANY_NAME}, our users, or the public.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">4. Data Retention</h2>
            <p className="text-muted-foreground leading-relaxed">
              We retain your personal data for as long as your account is active or as needed to provide you with the Services. If your Organization terminates its subscription, we will retain data for a minimum of 30 days to allow for export, after which data will be deleted or anonymized unless retention is required by law. Training completion records and certificates may be retained longer at the Organization's request for compliance purposes.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">5. Data Security</h2>
            <p className="text-muted-foreground leading-relaxed">
              We implement industry-standard security measures to protect your information, including:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Encryption of data in transit using TLS/SSL.</li>
              <li>Encrypted storage of passwords using bcrypt hashing.</li>
              <li>Access controls limiting data access to authorized personnel only.</li>
              <li>Regular security assessments and monitoring of our systems.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed">
              No method of transmission over the internet or electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your data, we cannot guarantee absolute security.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">6. Your Rights and Choices</h2>
            <p className="text-muted-foreground leading-relaxed">
              Depending on your jurisdiction, you may have the following rights regarding your personal data:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Access:</strong> Request a copy of the personal data we hold about you.</li>
              <li><strong>Correction:</strong> Request correction of inaccurate or incomplete data.</li>
              <li><strong>Deletion:</strong> Request deletion of your personal data, subject to legal retention obligations.</li>
              <li><strong>Portability:</strong> Request your data in a structured, machine-readable format.</li>
              <li><strong>Objection:</strong> Object to processing of your data for certain purposes.</li>
              <li><strong>Restriction:</strong> Request restriction of processing in certain circumstances.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed">
              To exercise these rights, contact us at <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline">{CONTACT_EMAIL}</a>. We will respond within 30 days. Note that some rights may be limited where we process your data on behalf of your employer.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">7. Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              We use the following types of cookies:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Essential cookies:</strong> Required for the platform to function. These cannot be disabled.</li>
              <li><strong>Authentication cookies:</strong> Used to maintain your login session securely.</li>
              <li><strong>Analytics cookies:</strong> Used to understand how users interact with the platform. You may opt out via your browser settings.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">8. Children's Privacy</h2>
            <p className="text-muted-foreground leading-relaxed">
              Our Services are not directed to individuals under the age of 16. We do not knowingly collect personal information from children. If we become aware that a child under 16 has provided us with personal data, we will delete such information promptly.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">9. International Data Transfers</h2>
            <p className="text-muted-foreground leading-relaxed">
              Your information may be transferred to and processed in countries other than your country of residence. We ensure appropriate safeguards are in place for such transfers in accordance with applicable data protection laws, including standard contractual clauses where required.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">10. Changes to This Policy</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update this Privacy Policy from time to time to reflect changes in our practices or legal requirements. We will notify you of material changes by posting the updated policy with a new effective date and, where appropriate, by email notification. Your continued use of the Services after such changes constitutes your acceptance of the updated policy.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">11. Contact Us</h2>
            <p className="text-muted-foreground leading-relaxed">
              If you have questions about this Privacy Policy or our data practices, please contact our Privacy team:
            </p>
            <div className="bg-muted/40 rounded-lg p-4 text-sm text-muted-foreground space-y-1">
              <p><strong className="text-foreground">{COMPANY_NAME} — Privacy Team</strong></p>
              <p>Email: <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline">{CONTACT_EMAIL}</a></p>
            </div>
          </section>

        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 py-6">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
          <p>© {new Date().getFullYear()} {COMPANY_NAME}. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link to="/terms" className="hover:text-foreground transition-colors">Terms of Service</Link>
            <Link to="/privacy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
            <Link to="/" className="hover:text-foreground transition-colors">Back to Login</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
