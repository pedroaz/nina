import { Button } from '@/components/shared/ui/button';
import { LandingPrimaryImageCtaSection } from '@/components/landing/cta/LandingPrimaryCta';
import {
  LandingPricingSection,
  LandingPricingPlan,
  LandingBentoGridSection,
  LandingBentoGridIconItem,
} from '@/components/landing';
import {
  LandingProductTourSection,
  LandingProductTourList,
  LandingProductTourTrigger,
  LandingProductTourContent
} from '@/components/landing/LandingProductTour';
import Image from '@/components/shared/Image';
import { getAllBlogPosts } from '@/lib/blog-data';

export default function Component() {
  const blogPosts = getAllBlogPosts();

  return (
    <>
      <LandingPrimaryImageCtaSection
        title="What if your German Teacher was a Dog?"
        description="Call Nina now!"
        imageSrc="/nina-teacher.png"
        imageAlt="Sample image"
        imagePerspective="left"
        imagePriority={true}
      >
        <Button size="xl" asChild>
          <a href="#">Start for Free</a>
        </Button>
      </LandingPrimaryImageCtaSection>

      <LandingProductTourSection
        title="Built for German Learners"
        description="Nina combines cutting-edge technology with language expertise to give you the best learning experience."
        defaultValue="feature-1"
      >
        <LandingProductTourList>
          <LandingProductTourTrigger value="feature-1">
            <p className="text-xl font-bold">
              Open Source Technologies
            </p>
            <p>
              Built on proven open-source frameworks for transparency, security, and continuous improvement.
            </p>
          </LandingProductTourTrigger>

          <LandingProductTourTrigger value="feature-2">
            <p className="text-xl font-bold">
              German Infrastructure
            </p>
            <p>
              Your data stays in Germany, ensuring GDPR compliance and lightning-fast response times.
            </p>
          </LandingProductTourTrigger>

          <LandingProductTourTrigger value="feature-3">
            <p className="text-xl font-bold">
              German-Optimized AI
            </p>
            <p>
              Advanced AI specifically tuned for German language learning with expertly crafted prompts.
            </p>
          </LandingProductTourTrigger>
        </LandingProductTourList>

        <LandingProductTourContent value="feature-1">
          <Image src="https://picsum.photos/id/180/800/800" width={800} height={800} alt="Open source technologies" />
        </LandingProductTourContent>

        <LandingProductTourContent value="feature-2">
          <Image src="https://picsum.photos/id/1/800/800" width={800} height={800} alt="German infrastructure" />
        </LandingProductTourContent>

        <LandingProductTourContent value="feature-3">
          <Image src="https://picsum.photos/id/20/800/800" width={800} height={800} alt="German-optimized AI" />
        </LandingProductTourContent>
      </LandingProductTourSection>

      <LandingBentoGridSection
        title="Powered by Modern Technologies"
        description="Nina is built on a foundation of cutting-edge, open-source technologies and reliable infrastructure."
      >
        <LandingBentoGridIconItem
          icon={<span className="text-5xl">🐙</span>}
          bottomText="GitHub"
          href="https://github.com"
        />
        <LandingBentoGridIconItem
          icon={<span className="text-5xl font-bold">▲</span>}
          bottomText="Next.js"
          href="https://nextjs.org"
        />
        <LandingBentoGridIconItem
          icon={<span className="text-5xl">🔥</span>}
          bottomText="Genkit"
          href="https://firebase.google.com/products/genkit"
        />
        <LandingBentoGridIconItem
          icon={<span className="text-5xl">🖥️</span>}
          bottomText="Hetzner"
          href="https://www.hetzner.com"
        />
        <LandingBentoGridIconItem
          icon={<span className="text-5xl">❄️</span>}
          bottomText="Coolify"
          href="https://coolify.io"
        />
      </LandingBentoGridSection>

      <section className="w-full py-12 lg:py-16 px-6">
        <div className="container mx-auto max-w-7xl">
          <div className="grid lg:grid-cols-2 gap-12">
            {/* Blog Section */}
            <div>
              <h2 className="text-3xl lg:text-4xl font-bold font-display mb-4">Learn from our Blog</h2>
              <p className="text-lg opacity-70 mb-8">
                Stay updated with the latest insights and tips for learning German with AI.
              </p>
              {blogPosts.length > 0 ? (
                <div className="space-y-4">
                  {blogPosts.map((post) => (
                    <a
                      key={post.slug}
                      href={`/blog/${post.slug}`}
                      className="block p-4 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-primary-500 dark:hover:border-primary-500 transition-colors"
                    >
                      <h3 className="font-bold text-lg mb-2">{post.title}</h3>
                      <p className="text-sm opacity-70 mb-2">{post.summary}</p>
                      <div className="flex items-center justify-between text-xs opacity-50">
                        <span>{post.date}</span>
                        <span>{post.readingTime} min read</span>
                      </div>
                    </a>
                  ))}
                </div>
              ) : (
                <p className="text-sm opacity-50">No blog posts yet.</p>
              )}
            </div>

            {/* Legal Section */}
            <div>
              <h2 className="text-3xl lg:text-4xl font-bold font-display mb-4">Legal Information</h2>
              <p className="text-lg opacity-70 mb-8">
                Review our privacy practices and terms of service.
              </p>
              <div className="space-y-4">
                <a
                  href="/privacy-policy"
                  className="block p-4 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-primary-500 dark:hover:border-primary-500 transition-colors"
                >
                  <h3 className="font-bold text-lg mb-2">Privacy Policy</h3>
                  <p className="text-sm opacity-70 mb-2">
                    Learn how we collect, use, and protect your personal data in compliance with GDPR.
                  </p>
                  <span className="text-xs text-primary-500">Read more →</span>
                </a>
                <a
                  href="/terms-of-service"
                  className="block p-4 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-primary-500 dark:hover:border-primary-500 transition-colors"
                >
                  <h3 className="font-bold text-lg mb-2">Terms of Service</h3>
                  <p className="text-sm opacity-70 mb-2">
                    Read the terms governing your use of Nina and our Services.
                  </p>
                  <span className="text-xs text-primary-500">Read more →</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      <LandingPricingSection
        title="Simple, flexible pricing"
        description="Choose the plan that works best for you. Start free or bring your own API key."
      >
        <LandingPricingPlan
          title="Free"
          description="Perfect for trying out Nina."
          price="€0"
        >
          <p>10 minutes of conversation per month</p>
          <p>Basic German lessons</p>
          <p>Community support</p>
        </LandingPricingPlan>

        <LandingPricingPlan
          title="BYOK"
          description="Bring your own OpenAI API key."
          ctaText="Get started"
          price="€0"
        >
          <p>Unlimited conversations</p>
          <p>Use your own API key</p>
          <p>All features included</p>
          <p>Full control over usage</p>
        </LandingPricingPlan>

        <LandingPricingPlan
          title="Premium"
          description="Full access, no setup needed."
          ctaText="Start learning"
          price="€4.80"
          priceSuffix="/mo"
        >
          <p>Unlimited conversations</p>
          <p>All premium features</p>
          <p>Priority support</p>
          <p>No API key required</p>
        </LandingPricingPlan>
      </LandingPricingSection>
    </>
  );
}