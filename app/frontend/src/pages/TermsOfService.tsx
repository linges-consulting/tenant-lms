import { Link } from 'react-router-dom';
import { GraduationCap, ArrowLeft } from 'lucide-react';

const EFFECTIVE_DATE = 'May 16, 2026';
const COMPANY_NAME = 'Enterprise Learning Platform';
const CONTACT_EMAIL = 'legal@customlms.com';

export function TermsOfService() {
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
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Terms of Service</h1>
          <p className="text-muted-foreground text-sm">
            Effective date: <strong>{EFFECTIVE_DATE}</strong>
          </p>
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none space-y-10 text-foreground">

          <section className="space-y-3">
            <p className="text-muted-foreground leading-relaxed">
              These Terms of Service ("Terms") govern your access to and use of the {COMPANY_NAME} learning management platform and associated services (collectively, the "Services") provided by {COMPANY_NAME} ("we," "our," or "us"). By accessing or using the Services, you agree to be bound by these Terms. If you do not agree to these Terms, you may not use the Services.
            </p>
            <p className="text-muted-foreground leading-relaxed">
              If you are using the Services on behalf of an organization (your "Organization"), you represent and warrant that you have the authority to bind that Organization to these Terms, and "you" and "your" will refer collectively to you and that Organization.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">1. Description of Services</h2>
            <p className="text-muted-foreground leading-relaxed">
              {COMPANY_NAME} is a B2B multi-tenant learning management system (LMS) designed to help organizations manage employee training, track compliance progress, issue certificates of completion, and monitor workforce development. The Services are made available to Organizations on a subscription basis and to individual users through invitations issued by their employing Organization.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">2. Eligibility and Account Registration</h2>
            <p className="text-muted-foreground leading-relaxed">
              Access to the Services requires an invitation from an authorized administrator within an Organization that has an active subscription. You may not create an account without a valid invitation. You represent that:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>You are at least 16 years of age.</li>
              <li>You have been authorized by your Organization to access the Services.</li>
              <li>All registration information you submit is accurate, current, and complete.</li>
              <li>You will maintain the accuracy of your information and promptly update it as necessary.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed">
              You are responsible for maintaining the confidentiality of your login credentials and for all activities that occur under your account. You must notify us immediately at <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline">{CONTACT_EMAIL}</a> if you believe your account has been compromised.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">3. Acceptable Use Policy</h2>
            <p className="text-muted-foreground leading-relaxed">
              You agree to use the Services only for lawful purposes and in accordance with these Terms. You must not:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Access or attempt to access accounts, data, or systems belonging to other users without authorization.</li>
              <li>Upload, transmit, or distribute any content that is unlawful, harmful, defamatory, obscene, or otherwise objectionable.</li>
              <li>Use automated tools, scrapers, bots, or other means to access or extract data from the Services without our express written consent.</li>
              <li>Interfere with or disrupt the integrity or performance of the Services or related infrastructure.</li>
              <li>Attempt to decompile, reverse-engineer, disassemble, or derive source code from any component of the Services.</li>
              <li>Circumvent, disable, or otherwise interfere with security-related features of the Services.</li>
              <li>Use the Services to transmit unsolicited communications or engage in any form of spam.</li>
              <li>Impersonate any person or entity or misrepresent your affiliation with any person or entity.</li>
              <li>Use the Services in any manner that could harm {COMPANY_NAME}, our partners, or other users.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">4. Organization Administrator Responsibilities</h2>
            <p className="text-muted-foreground leading-relaxed">
              Organizations that subscribe to the Services are responsible for:
            </p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Ensuring that all invited users comply with these Terms.</li>
              <li>Managing user access, roles, and permissions appropriately.</li>
              <li>Promptly revoking access for users who leave the Organization or no longer require access.</li>
              <li>Ensuring that any training content uploaded or created within the platform complies with applicable laws, including intellectual property rights and employment regulations.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">5. Intellectual Property</h2>
            <h3 className="text-base font-semibold text-foreground">5.1 Our Intellectual Property</h3>
            <p className="text-muted-foreground leading-relaxed">
              The Services, including all software, design elements, text, graphics, logos, and underlying technology, are owned by or licensed to {COMPANY_NAME} and are protected by applicable intellectual property laws. These Terms do not grant you any ownership rights in the Services. You are granted a limited, non-exclusive, non-transferable, revocable license to access and use the Services solely in accordance with these Terms.
            </p>
            <h3 className="text-base font-semibold text-foreground">5.2 Your Content</h3>
            <p className="text-muted-foreground leading-relaxed">
              You retain ownership of any training materials, content, or data you upload to the Services ("Your Content"). By uploading Your Content, you grant {COMPANY_NAME} a limited, worldwide, royalty-free license to store, display, and process Your Content solely as necessary to provide the Services to you and your Organization.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">6. Privacy</h2>
            <p className="text-muted-foreground leading-relaxed">
              Your use of the Services is also governed by our{' '}
              <Link to="/privacy" className="text-primary hover:underline">Privacy Policy</Link>, which is incorporated into these Terms by reference. By using the Services, you consent to our collection and use of your information as described in the Privacy Policy.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">7. Payment and Subscriptions</h2>
            <p className="text-muted-foreground leading-relaxed">
              Subscription fees for Organizations are governed by a separate Order Form or subscription agreement between {COMPANY_NAME} and the Organization. Individual users do not pay directly for the Services. All fees are non-refundable except as expressly stated in your Organization's agreement with us.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">8. Disclaimer of Warranties</h2>
            <p className="text-muted-foreground leading-relaxed uppercase text-xs leading-relaxed">
              THE SERVICES ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICES WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, OR FREE FROM VIRUSES OR OTHER HARMFUL COMPONENTS. WE MAKE NO WARRANTIES REGARDING THE ACCURACY, COMPLETENESS, OR RELIABILITY OF ANY CONTENT AVAILABLE THROUGH THE SERVICES.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">9. Limitation of Liability</h2>
            <p className="text-muted-foreground leading-relaxed uppercase text-xs leading-relaxed">
              TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, {COMPANY_NAME.toUpperCase()} AND ITS OFFICERS, DIRECTORS, EMPLOYEES, AGENTS, AND LICENSORS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, DATA, GOODWILL, OR BUSINESS OPPORTUNITIES, ARISING FROM OR RELATED TO YOUR USE OF OR INABILITY TO USE THE SERVICES, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
            </p>
            <p className="text-muted-foreground leading-relaxed uppercase text-xs">
              OUR TOTAL CUMULATIVE LIABILITY TO YOU FOR ALL CLAIMS ARISING UNDER OR RELATED TO THESE TERMS OR THE SERVICES SHALL NOT EXCEED THE GREATER OF (A) THE FEES PAID BY YOUR ORGANIZATION IN THE TWELVE MONTHS PRECEDING THE CLAIM, OR (B) ONE HUNDRED DOLLARS (USD $100).
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">10. Indemnification</h2>
            <p className="text-muted-foreground leading-relaxed">
              You agree to indemnify, defend, and hold harmless {COMPANY_NAME} and its officers, directors, employees, and agents from and against any claims, liabilities, damages, losses, costs, or expenses (including reasonable attorneys' fees) arising out of or relating to: (a) your use of the Services in violation of these Terms; (b) Your Content; (c) your violation of any third-party rights; or (d) your violation of any applicable law or regulation.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">11. Termination</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may suspend or terminate your access to the Services at any time, with or without cause, upon notice. Your access may be terminated immediately and without notice if you breach these Terms. Upon termination, your right to access the Services will cease. Provisions that by their nature should survive termination (including intellectual property, disclaimers, limitations of liability, and dispute resolution) will survive.
            </p>
            <p className="text-muted-foreground leading-relaxed">
              Your Organization may also revoke your access at any time. Termination of an Organization's subscription will result in suspension of all associated user accounts.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">12. Governing Law and Dispute Resolution</h2>
            <p className="text-muted-foreground leading-relaxed">
              These Terms are governed by and construed in accordance with the laws of the jurisdiction in which {COMPANY_NAME} is incorporated, without regard to conflict of law principles. Any dispute arising from or relating to these Terms or the Services that cannot be resolved informally shall be submitted to binding arbitration in accordance with the rules of a recognized arbitration body, and the arbitration shall take place in {COMPANY_NAME}'s principal place of business.
            </p>
            <p className="text-muted-foreground leading-relaxed">
              You and {COMPANY_NAME} agree to waive any right to a jury trial and to participate in a class action lawsuit or class-wide arbitration.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">13. Changes to These Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              We reserve the right to modify these Terms at any time. We will provide notice of material changes by updating the effective date and, where appropriate, notifying you via email or in-app notification. Your continued use of the Services after such changes take effect constitutes your acceptance of the revised Terms. If you do not agree to the revised Terms, you must stop using the Services.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">14. Miscellaneous</h2>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Entire Agreement:</strong> These Terms, together with our Privacy Policy and any applicable Order Form, constitute the entire agreement between you and {COMPANY_NAME} regarding the Services.</li>
              <li><strong>Severability:</strong> If any provision of these Terms is found to be unenforceable, that provision will be modified to the minimum extent necessary, and the remaining provisions will remain in full force.</li>
              <li><strong>No Waiver:</strong> Our failure to enforce any right or provision will not constitute a waiver of that right.</li>
              <li><strong>Assignment:</strong> You may not assign your rights under these Terms without our prior written consent. We may assign our rights without restriction.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">15. Contact Us</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions about these Terms, please contact our legal team:
            </p>
            <div className="bg-muted/40 rounded-lg p-4 text-sm text-muted-foreground space-y-1">
              <p><strong className="text-foreground">{COMPANY_NAME} — Legal Team</strong></p>
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
