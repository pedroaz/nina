import { Button } from '@/components/shared/ui/button';
import { LandingPrimaryImageCtaSection } from '@/components/landing/cta/LandingPrimaryCta';

export default function Component() {
  const avatarItems = [
    {
      imageSrc: 'https://picsum.photos/id/64/100/100',
      name: 'John Doe',
    },
    {
      imageSrc: 'https://picsum.photos/id/65/100/100',
      name: 'Jane Doe',
    },
    {
      imageSrc: 'https://picsum.photos/id/669/100/100',
      name: 'Alice Doe',
    },
  ];

  return (
    <>
      <LandingPrimaryImageCtaSection
        title="What if your German Teacher was a Dog?"
        description="Call Nina now!"
        imageSrc="/nina-teacher.png"
        imageAlt="Sample image"
        imagePerspective="left"
      >
        <Button size="xl" asChild>
          <a href="#">Start for Free</a>
        </Button>
      </LandingPrimaryImageCtaSection>
    </>
  );
}